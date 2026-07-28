"""The dashboard must be able to report training problems, not only green.

Covers the feedback fetch, the issue detection, and the both-sides render.
"""
from __future__ import annotations

from command_center import shaggoth
from command_center.shaggoth import (
    LearningCounter,
    ShaggothState,
    ShaggothStatus,
    parse_feedback_response,
)
from command_center.screens import training_health


def test_parse_feedback_handles_missing_endpoint():
    assert parse_feedback_response(None) == {"total": 0, "bad": 0, "repair_queue": 0}


def test_parse_feedback_reads_repair_queue():
    body = {"total": 12, "good": 1, "bad": 11, "repair_queue": 8}
    assert parse_feedback_response(body)["repair_queue"] == 8


def test_healthy_status_reports_no_problems():
    st = ShaggothStatus(state=ShaggothState.ONLINE, scheduler_enabled=True,
                        scheduler_alive=True, knowledge_entries=100,
                        fresh_entries=90, stale_entries=10)
    assert st.training_issues() == []


def test_stalled_is_reported():
    st = ShaggothStatus(state=ShaggothState.STALLED, scheduler_enabled=True,
                        scheduler_alive=True, detail="no research in 7h")
    issues = st.training_issues()
    assert any("STALLED" in i for i in issues)


def test_repair_backlog_is_reported_even_when_online():
    """A repair queue does not move the state off ONLINE -- it must still show."""
    st = ShaggothStatus(state=ShaggothState.ONLINE, scheduler_enabled=True,
                        scheduler_alive=True, knowledge_entries=100,
                        fresh_entries=99, stale_entries=1,
                        feedback_repair_queue=8)
    issues = st.training_issues()
    assert any("repair backlog" in i and "8" in i for i in issues)


def test_scrape_errors_and_stale_ratio_reported():
    st = ShaggothStatus(state=ShaggothState.ONLINE, scheduler_enabled=True,
                        scheduler_alive=True, knowledge_entries=800,
                        stale_entries=520, fresh_entries=280,
                        scrape_errors=12, last_scrape_error="Name or service not known")
    issues = st.training_issues()
    assert any("scrape error" in i for i in issues)
    assert any("stale" in i and "65%" in i for i in issues)


def test_dead_thread_is_reported():
    st = ShaggothStatus(state=ShaggothState.ONLINE, scheduler_enabled=True,
                        scheduler_alive=False)
    assert any("DEAD" in i for i in st.training_issues())


def test_training_health_shows_both_sides():
    st = ShaggothStatus(state=ShaggothState.ONLINE, scheduler_enabled=True,
                        scheduler_alive=True, knowledge_entries=807,
                        stale_entries=521, fresh_entries=286,
                        total_words=275035, total_episodes=212,
                        feedback_repair_queue=7, scrape_errors=12,
                        last_scrape_error="Name or service not known")
    counter = LearningCounter()
    counter.update(st)  # baseline; no growth yet
    lines = training_health(st, counter)
    text = "\n".join(lines)
    # good side present (a healthy line, since no growth this session)
    assert any(l.strip().startswith("+") for l in lines)
    # bad side present and enumerated
    assert "Issues:" in text
    assert "repair backlog" in text
    assert "scrape error" in text
    assert "stale" in text


def test_training_health_says_so_when_clean():
    st = ShaggothStatus(state=ShaggothState.ONLINE, scheduler_enabled=True,
                        scheduler_alive=True, knowledge_entries=100,
                        fresh_entries=100, stale_entries=0)
    lines = training_health(st, LearningCounter())
    assert any("No problems detected" in l for l in lines)
