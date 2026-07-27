"""The two alien narrators, their bubbles, cameos, and floor hygiene.

The scene is a pure function of the tick, so all of this is asserted
without a terminal. The load-bearing tests are the containment ones: the
aliens may be as silly as they like, but they must never leave the
animation grid or make the dashboard unreadable.
"""
from __future__ import annotations

from command_center import animation, shaggoth
from command_center.animation import (
    MIN_ALIEN_HEIGHT,
    MIN_ALIEN_WIDTH,
    OverlayStyle,
    last_line_for,
    speech_bubble,
)
from command_center.shaggoth import (
    EARTH_ALIEN,
    SATELLITE_ALIEN,
    LearningCounter,
    LearningFeed,
    ShaggothState,
    ShaggothStatus,
)

WIDE, TALL = 100, 14


def _frame(tick: int = 0, script=None, **kwargs):
    return animation.render(
        WIDE, TALL, tick,
        alien_script=script if script is not None else [(0, "hello"), (1, "hi")],
        **kwargs,
    )


# --------------------------------------------------------------------------
# Speech bubbles
# --------------------------------------------------------------------------


def test_speech_bubble_wraps_text() -> None:
    assert speech_bubble("learning DNA", 40) == "( learning DNA )"


def test_speech_bubble_truncates_rather_than_overflowing() -> None:
    bubble = speech_bubble("a very long sentence about photosynthesis", 20)
    assert len(bubble) <= 20
    assert bubble.startswith("( ") and bubble.endswith(" )")


def test_speech_bubble_declines_when_there_is_no_room() -> None:
    assert speech_bubble("anything", 6) == ""
    assert speech_bubble("", 40) == ""


def test_last_line_for_keeps_each_alien_talking() -> None:
    script = [(0, "first"), (1, "second"), (0, "third")]
    # At index 2 the Earth alien just spoke; the satellite's last line stands.
    assert last_line_for(script, 2, EARTH_ALIEN) == "third"
    assert last_line_for(script, 2, SATELLITE_ALIEN) == "second"


def test_last_line_for_wraps_and_survives_a_one_sided_script() -> None:
    assert last_line_for([(0, "solo")], 5, EARTH_ALIEN) == "solo"
    assert last_line_for([(0, "solo")], 5, SATELLITE_ALIEN) == ""
    assert last_line_for([], 0, EARTH_ALIEN) == ""


# --------------------------------------------------------------------------
# Scene containment -- the part that protects the dashboard
# --------------------------------------------------------------------------


def test_aliens_appear_on_both_sides() -> None:
    frame = _frame()
    styles = {span.style for span in frame.overlays}
    assert OverlayStyle.GREEN in styles    # Earth, left
    assert OverlayStyle.PURPLE in styles   # satellite, right

    green = min(s.col for s in frame.overlays if s.style is OverlayStyle.GREEN)
    purple = min(s.col for s in frame.overlays if s.style is OverlayStyle.PURPLE)
    assert green < WIDE // 2 < purple


def test_every_overlay_stays_inside_the_grid_across_many_ticks() -> None:
    script = [(0, "x" * 200), (1, "y" * 200)]
    for tick in range(0, 900, 7):
        frame = _frame(tick, script=script)
        assert len(frame.lines) == TALL
        for span in frame.overlays:
            assert 0 <= span.row < TALL
            assert 0 <= span.col
            assert span.col + len(span.text) <= WIDE
        for line in frame.lines:
            assert len(line) == WIDE


def test_bubbles_never_overlap_each_other() -> None:
    script = [(0, "left " * 30), (1, "right " * 30)]
    for tick in range(0, 400, 11):
        frame = _frame(tick, script=script)
        bubbles = [s for s in frame.overlays if s.style is OverlayStyle.YELLOW]
        occupied = [set(range(s.col, s.col + len(s.text))) for s in bubbles]
        for i, first in enumerate(occupied):
            for second in occupied[i + 1 :]:
                assert not (first & second)


def test_droppings_land_on_the_floor_row_only() -> None:
    """The mess belongs on the last animation row, right above the rule."""
    floor = TALL - 1
    seen_floor = False
    for tick in range(0, 600, 5):
        frame = _frame(tick)
        for span in frame.overlays:
            if span.style is OverlayStyle.AMBER:
                assert span.row == floor
                seen_floor = True
    assert seen_floor


def test_floor_is_eventually_mopped() -> None:
    counts = {
        sum(1 for s in _frame(tick).overlays if s.style is OverlayStyle.AMBER)
        for tick in range(0, animation.DROPPING_PERIOD * (animation.MAX_DROPPINGS + 1), 5)
    }
    assert 0 in counts          # cleared
    assert max(counts) > 0      # and it does accumulate


def test_stray_alien_cameo_comes_and_goes() -> None:
    def has_cameo(tick: int) -> bool:
        return any(s.style is OverlayStyle.BLUE for s in _frame(tick).overlays)

    assert has_cameo(0)
    assert not has_cameo(animation.PEEK_DURATION + 1)


def test_reduced_motion_keeps_the_narrators_but_drops_the_antics() -> None:
    frame = _frame(0, reduced_motion=True)
    styles = {span.style for span in frame.overlays}
    assert OverlayStyle.GREEN in styles
    assert OverlayStyle.BLUE not in styles   # no cameo
    assert OverlayStyle.AMBER not in styles  # no mess


def test_aliens_can_be_switched_off_entirely() -> None:
    assert _frame(0, aliens=False).overlays == []


def test_small_terminals_get_no_aliens() -> None:
    small = animation.render(
        MIN_ALIEN_WIDTH - 1, MIN_ALIEN_HEIGHT, 0, alien_script=[(0, "hi")]
    )
    assert small.overlays == []
    short = animation.render(
        MIN_ALIEN_WIDTH, MIN_ALIEN_HEIGHT - 1, 0, alien_script=[(0, "hi")]
    )
    assert short.overlays == []


def test_packets_never_double_draw_under_an_alien() -> None:
    from command_center.activity import AIFlowPhase

    for tick in range(0, 300, 3):
        frame = _frame(tick, flow_phase=AIFlowPhase.PROCESSING, cpu_percent=90, ram_percent=90)
        occupied = {
            (s.row, s.col + i) for s in frame.overlays for i in range(len(s.text))
        }
        assert not (occupied & set(frame.packet_cells))
        assert not (occupied & set(frame.trail_cells))


def test_scene_is_deterministic_in_tick() -> None:
    assert _frame(137).overlays == _frame(137).overlays


# --------------------------------------------------------------------------
# The script is built from real telemetry
# --------------------------------------------------------------------------


def test_script_quotes_the_real_numbers() -> None:
    status = ShaggothStatus(
        state=ShaggothState.ONLINE,
        knowledge_entries=307,
        total_words=238_431,
        total_episodes=1,
    )
    lines = " ".join(text for _who, text in shaggoth.alien_script(status, LearningCounter()))
    assert "307" in lines
    assert "238,431" in lines


def test_script_mentions_the_live_research_topic() -> None:
    status = ShaggothStatus(
        state=ShaggothState.LEARNING,
        is_researching=True,
        current_topic="aeroponic farming",
        knowledge_entries=307,
    )
    lines = shaggoth.alien_script(status, LearningCounter())
    assert any("aeroponic farming" in text for _who, text in lines)
    # The live topic leads the conversation rather than getting buried.
    assert "aeroponic farming" in lines[0][1]


def test_script_reports_scrape_failures() -> None:
    status = ShaggothStatus(
        state=ShaggothState.ONLINE,
        knowledge_entries=307,
        scrape_errors=11,
        last_scrape_error="HTTP Error 403: Blocked",
    )
    lines = " ".join(text for _who, text in shaggoth.alien_script(status, LearningCounter()))
    assert "403" in lines


def test_script_falls_back_when_shaggoth_is_down() -> None:
    lines = shaggoth.alien_script(
        ShaggothStatus(state=ShaggothState.OFFLINE, detail="API unreachable"),
        LearningCounter(),
    )
    assert lines  # never silent
    assert any("unreachable" in text for _who, text in lines)


def test_script_always_gives_both_aliens_something_to_say() -> None:
    cases = [
        ShaggothStatus(state=ShaggothState.ONLINE, knowledge_entries=307),
        ShaggothStatus(state=ShaggothState.IDLE),
        ShaggothStatus(state=ShaggothState.OFFLINE),
        ShaggothStatus(state=ShaggothState.STALLED, knowledge_entries=1, stale_entries=70),
    ]
    for status in cases:
        speakers = {who for who, _text in shaggoth.alien_script(status, LearningCounter())}
        assert speakers == {EARTH_ALIEN, SATELLITE_ALIEN}


def test_script_uses_the_ingestion_feed_when_it_has_one() -> None:
    feed = LearningFeed(events=["[42] OK   Photosynthesis: 2,388 words"], seeded=True)
    status = ShaggothStatus(state=ShaggothState.ONLINE, knowledge_entries=307)
    lines = " ".join(
        text for _who, text in shaggoth.alien_script(status, LearningCounter(), feed)
    )
    assert "Photosynthesis" in lines
