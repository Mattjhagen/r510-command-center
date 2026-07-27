"""Generative dialogue between Earth and the AI core.

The two figures in the animation are not reading a canned script. The one
on the right is Shaggoth itself: the command center asks its ``/chat``
endpoint a question, shows the real reply, then picks a subject out of that
reply and asks about *that* next. The conversation drifts wherever
Shaggoth's own knowledge takes it.

Every run opens on the same subject -- the novel Shaggoth has read -- so a
restart is a fresh starting point rather than a resumed transcript. Where
it goes from there depends entirely on what Shaggoth says.

Two properties matter more than the content:

1. **The render loop never blocks.** All HTTP happens on a daemon thread
   with a short timeout; the renderer only ever reads a snapshot.
2. **It degrades to something.** If Shaggoth is down or slow, the caller
   falls back to telemetry commentary, so the scene is never silent.
"""
from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

EARTH = 0   # asks
CORE = 1    # Shaggoth answers

# The book is the standing seed: every restart begins here.
SEED_QUESTION = "what is the gentle conquest"
SEED_REMARK = "so. you read the whole book."

DEFAULT_TURN_SECONDS = 20.0
DEFAULT_TIMEOUT = 20.0
MAX_LINES = 24
MAX_BUBBLE_CHARS = 110

#: Reply sources worth drifting from. "fallback" and "pattern" are Shaggoth
#: talking about itself rather than about the subject.
SUBSTANTIVE_SOURCES = frozenset({"knowledge", "model", "plugin"})

# Words that can never be the subject of a follow-up question. Without this
# the drift collapses almost immediately into asking about "the", "system",
# or whatever filler happened to be most frequent.
_STOPWORDS = {
    "about", "after", "again", "against", "all", "also", "always", "and", "another",
    "any", "are", "around", "because", "been", "before", "being", "between", "both",
    "but", "came", "can", "come", "could", "did", "does", "doing", "done", "down",
    "during", "each", "even", "ever", "every", "first", "for", "from", "get", "give",
    "goes", "going", "had", "has", "have", "her", "here", "him", "his", "how",
    "however", "into", "its", "just", "know", "last", "like", "made", "make", "many",
    "may", "might", "more", "most", "much", "must", "never", "new", "next", "not",
    "now", "off", "one", "only", "other", "our", "out", "over", "own", "part",
    "people", "perhaps", "put", "same", "said", "say", "see", "she", "should",
    "since", "some", "something", "still", "such", "take", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "thing", "things", "this",
    "those", "though", "three", "through", "time", "two", "under", "until", "use",
    "used", "very", "was", "way", "well", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your",
    # Bibliographic furniture. These are capitalised on a title page ("A Novel
    # by Matt Jhagen Overview"), so they look like proper nouns and the drift
    # kept asking "tell me about Novel".
    "appendix", "author", "book", "chapter", "contents", "edition", "epilogue",
    "foreword", "index", "novel", "overview", "preface", "prologue", "summary",
    "volume",
}

# A capitalised word that begins a *clause* rather than a name. These follow a
# sentence break often enough to survive the sentence-start filter, producing
# subjects like "When Ellie".
_CLAUSE_OPENERS = {
    "after", "although", "and", "as", "because", "before", "but", "despite",
    "during", "even", "for", "however", "if", "meanwhile", "once", "since",
    "so", "then", "though", "unless", "until", "when", "whenever", "where",
    "whereas", "which", "while", "yet",
}

_QUESTION_FORMS = (
    "what is {}",
    "tell me about {}",
    "why does {} matter",
    "what happens to {}",
    "explain {}",
    "what do you know about {}",
)

_EARTH_REACTIONS = (
    "go on.",
    "that's bleak.",
    "keep talking.",
    "and you're fine with that?",
    "hm.",
    "say more.",
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")
_PROPER_PHRASE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b")


def condense(text: str, max_chars: int = MAX_BUBBLE_CHARS) -> str:
    """Reduce a reply to the most it can say inside one speech bubble.

    Whole sentences are kept where they fit; a single over-long sentence is
    cut at a word boundary rather than mid-word.
    """
    text = " ".join((text or "").split())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    out = ""
    for sentence in _SENTENCE_END.split(text):
        candidate = f"{out} {sentence}".strip()
        if len(candidate) > max_chars:
            break
        out = candidate
    if out:
        return out

    clipped = text[:max_chars].rsplit(" ", 1)[0]
    return (clipped or text[:max_chars]).rstrip(",;:") + "…"


def _is_avoided(candidate: str, avoid: set) -> bool:
    """Whether ``candidate`` has effectively come up already.

    Compares by containment, not equality. What gets recorded is the whole
    question ("what is the gentle conquest"), so an exact-match check let the
    very next turn pick "The Gentle Conquest" straight back out of the answer
    and ask about it again. Containment in either direction catches that.
    """
    lowered = candidate.lower()
    for seen in avoid:
        if lowered == seen or lowered in seen:
            return True
        if len(seen) > 3 and seen in lowered:
            return True
    return False


def _sentence_starts(text: str) -> set:
    """Character offsets where a sentence begins."""
    starts = {0}
    for match in _SENTENCE_END.finditer(text):
        starts.add(match.end())
    return starts


def pick_subjects(text: str, avoid: Optional[set] = None, limit: int = 4) -> list:
    """Candidate subjects in a reply, best first.

    Proper-noun phrases win -- in a novel they are the characters, places,
    and named systems, which are what a conversation naturally moves to.
    Failing that, the longest unused content words, on the rough assumption
    that longer words are more specific.

    A *single* capitalised word at the start of a sentence is not a proper
    noun, it is just a sentence. Without that exclusion the conversation
    drifted into Shaggoth's own phrasing -- "Nothing on novel yet" became a
    question about "Nothing", then "Annoying", then "Genuinely".

    Returns ``[]`` when the reply offers nothing new, which the caller treats
    as a cue to reseed rather than repeat itself.
    """
    avoid = {a.lower() for a in (avoid or set())}
    text = text or ""
    starts = _sentence_starts(text)
    found: list = []

    def add(candidate: str) -> None:
        if len(found) >= limit:
            return
        if _is_avoided(candidate, avoid):
            return
        if any(candidate.lower() == f.lower() for f in found):
            return
        found.append(candidate)

    for match in _PROPER_PHRASE.finditer(text):
        phrase = match.group(0).strip()
        if match.start() in starts and " " not in phrase:
            continue  # sentence-initial single word: not a name
        words = phrase.split()
        if words[0].lower() in _CLAUSE_OPENERS:
            # "When Ellie ..." is a clause, not a name. Drop the opener and
            # keep the rest if anything real is left.
            words = words[1:]
            if not words:
                continue
            phrase = " ".join(words)
        if all(word.lower() in _STOPWORDS for word in words):
            continue
        add(phrase)

    # Fallback: the longest plain content words. Capitalised words are skipped
    # here -- a genuine proper noun was already collected by the phrase pass
    # above, so anything capitalised still left is a sentence opener
    # ("Nothing on novel yet. Annoying.") rather than a subject.
    for word in sorted(_WORD.findall(text), key=len, reverse=True):
        if word[0].isupper():
            continue
        if len(word) > 4 and word.lower() not in _STOPWORDS:
            add(word)

    return found[:limit]


def pick_subject(text: str, avoid: Optional[set] = None) -> str:
    """The single best subject in a reply, or ``""``."""
    subjects = pick_subjects(text, avoid, limit=1)
    return subjects[0] if subjects else ""


def next_question(subject: str, turn: int) -> str:
    """Phrase a follow-up about ``subject``, rotating through question forms."""
    if not subject:
        return SEED_QUESTION
    return _QUESTION_FORMS[turn % len(_QUESTION_FORMS)].format(subject)


def earth_reaction(turn: int) -> str:
    return _EARTH_REACTIONS[turn % len(_EARTH_REACTIONS)]


@dataclass
class ConversationState:
    """Snapshot handed to the renderer. Never mutated by the reader."""

    lines: list = field(default_factory=list)
    turn: int = 0
    live: bool = False


class ConversationEngine:
    """Drives the drifting dialogue on a background thread.

    ``start()`` is fire-and-forget; ``script()`` is safe to call from the
    render loop at any frame rate and never blocks on the network.
    """

    def __init__(
        self,
        base_url: str,
        turn_seconds: float = DEFAULT_TURN_SECONDS,
        timeout: float = DEFAULT_TIMEOUT,
        session_id: str = "command-center",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._turn_seconds = max(5.0, turn_seconds)
        self._timeout = timeout
        self._session_id = session_id

        self._lock = threading.Lock()
        self._lines: list = []
        self._turn = 0
        self._live = False
        self._asked: set = set()
        #: Subjects harvested from good answers, asked about in turn.
        self._queue: list = []
        self._last_reply = ""
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- public ------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="shaggoth-dialogue", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def script(self) -> list:
        """The conversation so far as ``(speaker, text)`` pairs."""
        with self._lock:
            return list(self._lines)

    @property
    def live(self) -> bool:
        """True once Shaggoth has actually answered at least once."""
        with self._lock:
            return self._live

    # -- internals ---------------------------------------------------------

    def _append(self, speaker: int, text: str) -> None:
        text = condense(text)
        if not text:
            return
        with self._lock:
            self._lines.append((speaker, text))
            if len(self._lines) > MAX_LINES:
                del self._lines[: len(self._lines) - MAX_LINES]

    def _ask(self, message: str) -> tuple:
        """POST to ``/chat``. Returns ``(reply, source)``.

        ``("", "")`` on any failure -- the caller handles a silent turn by
        reseeding, and a dashboard must not die because its AI is briefly
        unreachable.
        """
        payload = json.dumps(
            {"message": message, "session_id": self._session_id, "mode": "no_drift"}
        ).encode()
        request = urllib.request.Request(
            f"{self._base_url}/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return "", ""
        if not isinstance(body, dict):
            return "", ""
        return str(body.get("reply") or ""), str(body.get("source") or "")

    def turn(self, question: str) -> str:
        """Run one exchange and return the question to ask next.

        Separated from the loop so a whole conversation can be driven
        deterministically in tests without threads, sleeps, or a network.
        """
        self._append(EARTH, question)
        reply, source = self._ask(question)

        if not reply:
            with self._lock:
                self._live = False
            # An unreachable Shaggoth must not wedge the conversation on a
            # question it can never answer.
            return SEED_QUESTION

        with self._lock:
            self._live = True
            self._turn += 1
            turn = self._turn
        self._append(CORE, reply)
        self._asked.add(question)
        self._append(EARTH, earth_reaction(turn))

        # Only a substantive answer is allowed to steer the conversation.
        # A "don't know that yet" reply is about Shaggoth, not about the
        # subject, so mining it for the next question is how the dialogue
        # ended up asking "why does Nothing matter".
        repeated = reply.strip() == self._last_reply
        self._last_reply = reply.strip()

        # A repeat is the retrieval falling back on the same entry, not a new
        # answer. Mining it again just re-queues subjects already exhausted.
        if source in SUBSTANTIVE_SOURCES and not repeated:
            for subject in pick_subjects(reply, self._asked):
                if subject not in self._queue:
                    self._queue.append(subject)

        while self._queue:
            subject = self._queue.pop(0)
            if _is_avoided(subject, {a.lower() for a in self._asked}):
                continue
            self._asked.add(subject)
            return next_question(subject, turn)

        # Out of threads to pull. Back to the book.
        self._asked.clear()
        return SEED_QUESTION

    def _run(self) -> None:
        question = SEED_QUESTION
        self._append(EARTH, SEED_REMARK)
        while not self._stop.is_set():
            question = self.turn(question)
            self._stop.wait(self._turn_seconds)
