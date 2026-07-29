"""The Shaggoth detail screen ([G]) must show it's running, which model,
and how long it's been up -- covers shaggoth_report()'s SERVICE/MODEL and
SELF-GRADING CRITIC sections.
"""
from __future__ import annotations

from command_center.config import Config
from command_center.screens import shaggoth_report
from command_center.shaggoth import LearningCounter, ShaggothState, ShaggothStatus


def _report(status: ShaggothStatus) -> str:
    return "\n".join(shaggoth_report(Config(), status, LearningCounter()))


def test_offline_report_has_no_uptime_line():
    status = ShaggothStatus(state=ShaggothState.OFFLINE, detail="shaggoth API unreachable")
    text = _report(status)
    assert "Uptime" not in text


def test_error_state_still_shows_uptime_when_known():
    """Active-but-unreachable with a real uptime points at a crash-loop or
    port collision, not a fresh restart -- worth showing even though down."""
    status = ShaggothStatus(
        state=ShaggothState.ERROR, detail="service active but API unreachable",
        uptime_seconds=3 * 86400,
    )
    text = _report(status)
    assert "Uptime" in text
    assert "3d" in text


def test_healthy_report_shows_uptime_and_generation_model():
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        uptime_seconds=4321.0,
        generation_model="openai", generation_openai=True,
        generation_openai_model="gpt-4o-mini", generation_configured=True,
    )
    text = _report(status)
    assert "Uptime       1h 12m" in text
    assert "Model        openai:gpt-4o-mini" in text


def test_healthy_report_shows_markov_when_no_gpt_backend():
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        generation_model="markov",
    )
    text = _report(status)
    assert "Model        markov" in text


def test_report_shows_critic_not_configured_on_older_shaggoth():
    status = ShaggothStatus(state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True)
    text = _report(status)
    assert "SELF-GRADING CRITIC" in text
    assert "Not configured" in text


def test_report_shows_critic_running_with_model_and_tally():
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        critic_model="claude-haiku-4-5-20251001", critic_running=True, critic_available=True,
        critic_judged=20, critic_good=1, critic_weak=3, critic_bad=16,
    )
    text = _report(status)
    assert "claude-haiku-4-5-20251001" in text
    assert "running" in text
    assert "NOT RUNNING" not in text
    assert "Judged 20" in text
    assert "good 1" in text and "weak 3" in text and "bad 16" in text


def test_report_flags_critic_configured_but_not_running():
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        critic_model="qwen2.5-coder:7b", critic_running=False,
    )
    text = _report(status)
    assert "NOT RUNNING" in text


def test_report_flags_critic_running_but_model_unavailable():
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        critic_model="qwen2.5-coder:7b", critic_running=True, critic_available=False,
    )
    text = _report(status)
    assert "model unavailable" in text


def test_report_omits_tally_when_nothing_judged_yet():
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        critic_model="qwen2.5-coder:7b", critic_running=True, critic_available=True,
        critic_judged=0,
    )
    text = _report(status)
    assert "Judged" not in text
