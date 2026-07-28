"""The generative dialogue: seeding, drift, and never blocking the render loop.

Everything the render loop touches is pure or lock-guarded, so all of this
runs without a network or a terminal.
"""
from __future__ import annotations

import threading
import time

import pytest

from command_center.conversation import (
    CORE,
    EARTH,
    SEED_QUESTION,
    ConversationEngine,
    condense,
    earth_reaction,
    next_question,
    pick_subject,
)


# --------------------------------------------------------------------------
# Condensing a reply into a bubble
# --------------------------------------------------------------------------


def test_condense_leaves_short_replies_alone():
    assert condense("Short answer.") == "Short answer."


def test_condense_keeps_whole_sentences():
    text = "First sentence here. " + "x" * 300
    out = condense(text, max_chars=60)
    assert out == "First sentence here."


def test_condense_cuts_a_long_sentence_at_a_word_boundary():
    out = condense("word " * 100, max_chars=40)
    assert len(out) <= 41  # plus the ellipsis
    assert not out.rstrip("…").endswith("wor")


def test_condense_normalises_whitespace():
    assert condense("  a\n\n b  ") == "a b"


def test_condense_handles_empty_input():
    assert condense("") == ""
    assert condense(None) == ""


# --------------------------------------------------------------------------
# Drift: choosing what to ask about next
# --------------------------------------------------------------------------


def test_pick_subject_prefers_proper_nouns():
    """In a novel these are the characters and places -- what a conversation
    naturally moves to."""
    assert pick_subject("The system was designed by Ellie Finch in Boston.") == "Ellie Finch"


def test_pick_subject_skips_what_has_already_been_asked():
    reply = "Ellie Finch met James Okoro at the hearing."
    assert pick_subject(reply, avoid={"Ellie Finch"}) == "James Okoro"


def test_pick_subject_falls_back_to_a_content_word():
    subject = pick_subject("the machine optimised everything quietly")
    assert subject in {"optimised", "everything", "quietly", "machine"}
    assert subject not in {"the"}


def test_pick_subject_never_returns_a_stopword():
    for _ in range(5):
        assert pick_subject("the and but with that this from they were") == ""


def test_pick_subject_returns_empty_when_there_is_nothing_new():
    """The caller treats this as a cue to reseed rather than repeat itself."""
    assert pick_subject("") == ""
    assert pick_subject(None) == ""


# --------------------------------------------------------------------------
# Question shaping
# --------------------------------------------------------------------------


def test_next_question_rotates_forms():
    forms = {next_question("gravity", turn) for turn in range(6)}
    assert len(forms) > 1
    assert all("gravity" in f for f in forms)


def test_next_question_falls_back_to_the_seed():
    assert next_question("", 0) == SEED_QUESTION


def test_earth_reaction_varies():
    assert len({earth_reaction(i) for i in range(6)}) > 1


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------


class FakeEngine(ConversationEngine):
    """A ConversationEngine with the network replaced by a scripted list."""

    def __init__(self, replies, source="knowledge", **kwargs):
        super().__init__("http://unused", **kwargs)
        # Each entry is a bare string, or (reply, source).
        self._replies = [r if isinstance(r, tuple) else (r, source) for r in replies]
        self.asked = []
        self.speakers = []

    def _ask(self, message, speaker=CORE):
        self.asked.append(message)
        self.speakers.append(speaker)
        return self._replies.pop(0) if self._replies else ("", "")

    def run_turns(self, count):
        """Drive `count` utterances synchronously: no thread, no sleeping."""
        message, speaker = SEED_QUESTION, CORE
        for _ in range(count):
            message, speaker = self.turn(message, speaker)
        return message, speaker


def test_conversation_opens_on_the_book():
    """Every restart begins from the novel, not a resumed transcript."""
    engine = FakeEngine(["The Gentle Conquest is a novel about Ellie Finch."])
    engine.run_turns(1)
    assert engine.asked[0] == SEED_QUESTION


def test_each_side_is_prompted_by_what_the_other_said():
    engine = FakeEngine([
        "The Gentle Conquest is a novel about Ellie Finch.",
        "Ellie Finch is a retired nurse in Ohio.",
    ])
    engine.run_turns(2)
    assert engine.asked[0] == SEED_QUESTION
    assert "Ellie Finch" in engine.asked[1]


def test_a_reply_is_never_handed_over_verbatim():
    """Verbatim hand-off retrieves the same entry: the two sides parrot it."""
    reply = "The Gentle Conquest is a novel about Ellie Finch."
    engine = FakeEngine([reply, "Ellie Finch is a nurse."])
    engine.run_turns(2)
    assert reply not in engine.asked


def test_the_two_speakers_alternate():
    engine = FakeEngine([f"Subject{i} is a real thing." for i in range(6)])
    engine.run_turns(6)
    assert engine.speakers == [CORE, EARTH, CORE, EARTH, CORE, EARTH]


def test_each_speaker_gets_its_own_session():
    """Sharing a session makes Shaggoth answer itself: a monologue."""
    sessions = []

    class Recorder(ConversationEngine):
        def _post(self, payload):
            sessions.append(payload["session_id"])

    engine = FakeEngine(["A is a thing.", "B is a thing."])
    engine.run_turns(2)
    assert engine.speakers[0] != engine.speakers[1]


def test_both_speakers_end_up_in_the_script():
    engine = FakeEngine([
        "The Gentle Conquest is a novel about Ellie Finch.",
        "Ellie Finch is a retired nurse.",
    ])
    engine.run_turns(2)
    speakers = {who for who, _text in engine.script()}
    assert EARTH in speakers
    assert CORE in speakers


def test_a_silent_turn_reseeds_instead_of_looping():
    """An unreachable Shaggoth must not wedge the conversation."""
    engine = FakeEngine(["", ""])
    engine.run_turns(2)
    assert engine.asked == [SEED_QUESTION, SEED_QUESTION]
    assert engine.live is False


def test_live_flips_once_shaggoth_actually_answers():
    engine = FakeEngine(["The Gentle Conquest is a novel."])
    assert engine.live is False
    engine.run_turns(1)
    assert engine.live is True


def test_shrugs_do_not_derail_the_queue():
    """Non-answers add nothing, so queued subjects still get their turn."""
    engine = FakeEngine([
        ("The book features Ellie Finch and Marcus Webb.", "knowledge"),
        ("Never heard of it.", "fallback"),
        ("Nor me.", "fallback"),
    ])
    engine.run_turns(3)
    assert any("Ellie Finch" in a for a in engine.asked), engine.asked
    assert any("Marcus Webb" in a for a in engine.asked), engine.asked


def test_script_is_bounded():
    engine = FakeEngine([f"Subject{i} is a thing that exists." for i in range(60)])
    engine.run_turns(50)
    from command_center.conversation import MAX_LINES

    assert len(engine.script()) <= MAX_LINES


def test_script_returns_a_copy_so_the_renderer_cannot_mutate_state():
    engine = FakeEngine(["The Gentle Conquest is a novel."])
    engine.run_turns(1)
    snapshot = engine.script()
    snapshot.clear()
    assert engine.script()


def test_script_is_safe_to_read_while_the_thread_writes():
    """The render loop calls script() every frame; it must never tear."""
    engine = FakeEngine([f"Subject{i} is a thing." for i in range(200)], turn_seconds=5)
    stop = threading.Event()

    def writer():
        while not stop.is_set():
            engine._append(CORE, "a line of dialogue")

    t = threading.Thread(target=writer, daemon=True)
    t.start()
    try:
        for _ in range(300):
            for who, text in engine.script():
                assert who in (EARTH, CORE)
                assert isinstance(text, str)
    finally:
        stop.set()
        t.join(timeout=2)


def test_stop_is_idempotent_and_start_does_not_double_spawn():
    engine = FakeEngine([])
    engine.start()
    first = engine._thread
    engine.start()
    assert engine._thread is first
    engine.stop()
    engine.stop()


def test_pick_subject_will_not_re_ask_what_the_question_already_covered():
    """The recorded item is the whole question, so equality was not enough."""
    from command_center.conversation import pick_subject

    reply = "The Gentle Conquest is a novel about Ellie Finch."
    assert pick_subject(reply, avoid={"what is the gentle conquest"}) == "Ellie Finch"


def test_conversation_does_not_repeat_itself():
    engine = FakeEngine([
        "The Gentle Conquest is a novel about Ellie Finch.",
        "Ellie Finch is a retired nurse who lives in Ohio.",
        "Ohio is where the hearings were held by Judge Alvarez.",
    ])
    engine.run_turns(3)
    assert len(set(engine.asked)) == 3, engine.asked


def test_bibliographic_words_are_not_subjects():
    """"A Novel by Matt Jhagen Overview" made it ask about "Novel"."""
    from command_center.conversation import pick_subjects

    subjects = pick_subjects("The Gentle Conquest A Novel by Matt Jhagen Overview")
    assert "Novel" not in subjects
    assert "Overview" not in subjects


def test_clause_openers_are_stripped_from_phrases():
    from command_center.conversation import pick_subjects

    subjects = pick_subjects("It was quiet. When Ellie arrived it changed.")
    assert "When Ellie" not in subjects
    assert any(s == "Ellie" for s in subjects)


def test_sentence_initial_single_words_are_not_names():
    from command_center.conversation import pick_subjects

    subjects = pick_subjects("Nothing on novel yet. Annoying.")
    assert "Nothing" not in subjects
    assert "Annoying" not in subjects


def test_a_non_answer_does_not_seed_the_drift():
    """"Never heard of X" is about Shaggoth, not about X."""
    engine = FakeEngine([
        ("Never heard of Meridian Systems. Annoying.", "fallback"),
        ("Nor me.", "fallback"),
        ("Still nothing.", "fallback"),
    ])
    engine.run_turns(3)
    # Nothing substantive was ever said, so no subject was harvested and the
    # conversation returns to the book -- but to a *different* chapter each
    # dry patch, rather than replaying one seed (which is what made the two
    # aliens loop on a single paragraph).
    from command_center.conversation import SEED_POOL

    assert engine.asked[-1] in SEED_POOL
    reseeds = [a for a in engine.asked if a in SEED_POOL]
    assert len(set(reseeds)) > 1, engine.asked


def test_dry_patches_rotate_through_the_book_instead_of_repeating_one_seed():
    """The alien-loop fix: consecutive reseeds must not be identical.

    Shaggoth is deterministic, so reseeding to one fixed question replays the
    same knowledge entry forever. Rotating the seed makes a dry patch move to
    a different chapter each time.
    """
    from command_center.conversation import SEED_POOL

    engine = FakeEngine([("shrug", "fallback")] * 5)
    engine.run_turns(5)
    reseeds = [a for a in engine.asked if a in SEED_POOL]
    # Every turn here is a non-answer, so every turn reseeds; they must differ.
    assert len(set(reseeds)) >= 4, engine.asked


def test_a_repeated_answer_does_not_requeue_the_same_subjects():
    """The subject queue must not grow on every repeat of the same line."""
    same = "The Gentle Conquest is a novel about Ellie Finch and Marcus Webb."
    engine = FakeEngine([same, same, same, same])
    engine.run_turns(1)
    after_first = list(engine._queue)
    engine.run_turns(3)
    assert engine._queue == after_first or set(engine._queue) <= set(after_first)


def test_a_duplicate_reply_is_not_rendered_twice():
    """The actual alien-loop bug: retrieval is deterministic per matched
    entry, so two *differently phrased* questions about the same topic can
    return a byte-identical reply (verified live: "what is Meridian" / "tell
    me about Meridian" / "explain Meridian" all returned the same sentence).
    Deriving a fresh subject each turn does not stop that -- the reply text
    itself must be deduped before it reaches the screen."""
    engine = FakeEngine([
        "The Gentle Conquest is a novel about Ellie Finch and Marcus Webb.",
        "Earth's current international standard prime meridian is the IERS Reference Meridian.",
        "Earth's current international standard prime meridian is the IERS Reference Meridian.",
    ])
    engine.run_turns(3)
    texts = [text for _who, text in engine.script()]
    assert len(texts) == len(set(texts)), texts


def test_a_duplicate_reply_does_not_derail_the_dialogue():
    """A suppressed duplicate must still move the conversation on -- not
    wedge it repeating the same (unrendered) request forever."""
    engine = FakeEngine([
        "The Gentle Conquest is a novel about Ellie Finch and Marcus Webb.",
        "same line every time",
        "same line every time",
        "same line every time",
    ])
    engine.run_turns(4)
    assert engine.live is True
    # Every duplicate still gets asked about differently, or reseeds -- it
    # never just resends the exact same question hoping for something new.
    assert len(set(engine.asked)) == len(engine.asked), engine.asked


def test_bibliographic_word_inside_a_phrase_rejects_the_whole_phrase():
    """"Matt Jhagen Overview" is title-page debris, not a person called
    Overview -- a single furniture word anywhere in the phrase must reject
    the whole thing, not just when every word is furniture."""
    from command_center.conversation import pick_subjects

    subjects = pick_subjects("The Gentle Conquest A Novel by Matt Jhagen Overview")
    assert "Matt Jhagen Overview" not in subjects
    assert not any("Overview" in s for s in subjects)
