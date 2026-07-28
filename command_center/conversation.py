"""Generative dialogue between Earth and the AI core.

Neither figure is reading a script. Both are Shaggoth, held in two separate
``/chat`` sessions and pointed at each other: whatever one says is sent to
the other as its next message, and the reply becomes that speaker's line.
The conversation is a real back-and-forth, and it drifts wherever
Shaggoth's own knowledge takes it.

Two sessions rather than one because ``/chat`` keeps per-session memory --
sharing a session would have it answering its own questions inside one
context and collapsing into a monologue.

Each speaker is prompted with a *subject* pulled out of what the other just
said, never with the reply itself: handing a reply over verbatim retrieves
the same knowledge entry, and the two sides parrot one paragraph forever.
Only the prompt is derived -- every line on screen is Shaggoth's own words.

Deriving the prompt is not sufficient on its own, though: retrieval is
deterministic per matched knowledge entry, so two differently phrased
questions about the same underlying topic ("what is Meridian" / "tell me
about Meridian" / "explain Meridian") can still return a byte-identical
reply. A short window of recently shown lines is kept so a duplicate is
caught and skipped rather than rendered again.

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
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

EARTH = 0   # asks
CORE = 1    # Shaggoth answers

# The book is the standing seed: every restart begins here.
SEED_QUESTION = "what is the gentle conquest"
SEED_REMARK = "so. you read the whole book."

# When the drift runs dry (no new subject to pull on), the conversation
# reseeds. Reseeding to a *single* fixed question is what made the two aliens
# repeat: Shaggoth is deterministic, so the same seed retrieves the same
# knowledge entry and the same definitional sentence every time -- the screen
# showed one paragraph over and over. Instead, rotate through subjects drawn
# from the novel Shaggoth has actually ingested (verified live to return
# source="knowledge", not the ~6 canned fallbacks). Each reseed lands on a
# different chapter, so a dry patch moves the scene forward instead of looping.
#
# NO_DRIFT is deliberate here (the generative model is not coherent -- see
# AGENTS.md sections HH and the retrain gate), so the only way to keep the
# exchange varied without a model is to feed it varied, in-knowledge seeds.
SEED_POOL = (
    SEED_QUESTION,
    "tell me about the shepherd",
    "tell me about the turning point",
    "tell me about the friendship gap",
    "tell me about the disappeared",
    "tell me about the compromise",
    "tell me about the wilderness",
    "tell me about the model citizen",
)

DEFAULT_TURN_SECONDS = 20.0
DEFAULT_TIMEOUT = 20.0
MAX_LINES = 24
MAX_BUBBLE_CHARS = 110

#: Reply sources worth drifting from. "fallback" and "pattern" are Shaggoth
#: talking about itself rather than about the subject.
SUBSTANTIVE_SOURCES = frozenset({"knowledge", "model", "plugin"})


# Bibliographic/title-page furniture. These are capitalised on a title page
# ("A Novel by Matt Jhagen Overview"), so they look like proper nouns. A
# *single* one of these inside an otherwise name-shaped phrase still means
# the phrase is title-page debris, not a name -- "Matt Jhagen Overview" kept
# looping the dialogue back to the book's own title-page entry, because the
# old filter only rejected a phrase where *every* word was a stopword.
_TITLE_FURNITURE = {
    "appendix", "author", "book", "chapter", "contents", "edition", "epilogue",
    "foreword", "index", "novel", "overview", "preface", "prologue", "summary",
    "volume",
}

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
} | _TITLE_FURNITURE

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
        if any(word.lower() in _TITLE_FURNITURE for word in words):
            continue
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
        #: Which book seed the next dry-patch reseed will use. Starts at 1 so
        #: the first reseed advances off SEED_QUESTION (already used to open)
        #: rather than repeating it.
        self._seed_idx = 1
        #: Subjects harvested from good answers, asked about in turn.
        self._queue: list = []
        #: Normalized text of recently *shown* lines. Retrieval is
        #: deterministic per matched entry, so two differently phrased
        #: questions about the same topic can return a byte-identical reply
        #: -- bounded to the same window as what is still on screen, so a
        #: duplicate is never rendered while it would still be visible.
        self._recent_texts: deque = deque(maxlen=MAX_LINES)
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

    def _ask(self, message: str, speaker: int = CORE) -> tuple:
        """POST to ``/chat``. Returns ``(reply, source)``.

        ``("", "")`` on any failure -- the caller handles a silent turn by
        reseeding, and a dashboard must not die because its AI is briefly
        unreachable.
        """
        # A session per speaker: /chat keeps per-session memory, and sharing
        # one would have Shaggoth answering its own questions inside a single
        # context, which reads as a monologue rather than a conversation.
        payload = json.dumps({
            "message": message,
            "session_id": f"{self._session_id}-{'core' if speaker == CORE else 'earth'}",
            "mode": "no_drift",
            # This dialogue runs continuously and is nobody's actual question.
            # Without opting out, every word it pulled out of a reply became a
            # research topic and the knowledge base filled with entries like
            # "understanding" and "geophysicists".
            "research": False,
        }).encode()
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

    def turn(self, message: str, speaker: int = CORE) -> tuple:
        """Run one utterance. Returns ``(next_message, next_speaker)``.

        ``speaker`` is who is about to talk; ``message`` is what the other
        one just said to them. Separated from the loop so a whole
        conversation can be driven deterministically in tests without
        threads, sleeps, or a network.
        """
        reply, source = self._ask(message, speaker)

        if not reply:
            with self._lock:
                self._live = False
            # An unreachable Shaggoth must not wedge the conversation on a
            # message it can never answer.
            return SEED_QUESTION, CORE

        with self._lock:
            self._live = True
            self._turn += 1
            turn = self._turn

        normalized = " ".join(reply.split()).lower()
        # Verified live: "what is Meridian" / "tell me about Meridian" /
        # "explain Meridian" -- three distinct question forms -- returned a
        # byte-identical reply, because the underlying retrieval is keyed to
        # the matched entry, not the phrasing. Deriving a fresh subject each
        # turn (below) does not prevent that; only checking the reply itself
        # does. A duplicate is treated like a non-answer: not rendered,
        # nothing harvested from it.
        is_duplicate = bool(normalized) and normalized in self._recent_texts

        if not is_duplicate:
            self._append(speaker, reply)
            self._recent_texts.append(normalized)
        self._asked.add(message.lower())

        substantive = not is_duplicate and source in SUBSTANTIVE_SOURCES

        if substantive:
            # Only a real answer is allowed to steer. A "don't know that yet"
            # reply is about Shaggoth, not about the subject, which is how the
            # dialogue once ended up asking "why does Nothing matter".
            for subject in pick_subjects(reply, self._asked):
                if subject not in self._queue:
                    self._queue.append(subject)

        other = EARTH if speaker == CORE else CORE

        # The next speaker is prompted with a *subject* drawn from what was
        # just said -- never with the reply itself. Handing the reply over
        # verbatim retrieves the same knowledge entry, so the two sides
        # parroted the same paragraph back and forth. Both lines are still
        # entirely Shaggoth's own words; only the prompt is derived.
        while self._queue:
            subject = self._queue.pop(0)
            if _is_avoided(subject, {a.lower() for a in self._asked}):
                continue
            self._asked.add(subject.lower())
            return next_question(subject, turn), other

        # Nothing new to pull on. Back to the book -- but to a *different*
        # part of it than last time, so a dry patch does not replay one
        # paragraph. (A silent/unreachable Shaggoth is handled above and holds
        # the base seed; rotating only happens when Shaggoth is answering.)
        self._asked.clear()
        return self._next_seed(), other

    def _next_seed(self) -> str:
        """The next book seed to reseed from, rotating through SEED_POOL."""
        seed = SEED_POOL[self._seed_idx % len(SEED_POOL)]
        self._seed_idx += 1
        return seed

    def _run(self) -> None:
        self._append(EARTH, SEED_REMARK)
        message, speaker = SEED_QUESTION, CORE
        while not self._stop.is_set():
            message, speaker = self.turn(message, speaker)
            self._stop.wait(self._turn_seconds)
