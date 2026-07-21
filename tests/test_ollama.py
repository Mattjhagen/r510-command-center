"""Tests for Ollama status detection and API response parsing."""
from __future__ import annotations

import subprocess

from command_center.ollama import (
    OllamaState,
    get_status,
    parse_ps_response,
    parse_tags_response,
    systemctl_is_active,
)


def test_parse_tags_response_extracts_names() -> None:
    data = {"models": [{"name": "llama3:8b"}, {"name": "gemma:2b"}]}
    assert parse_tags_response(data) == ["llama3:8b", "gemma:2b"]


def test_parse_tags_response_handles_missing_or_empty() -> None:
    assert parse_tags_response(None) == []
    assert parse_tags_response({}) == []
    assert parse_tags_response({"models": []}) == []


def test_parse_tags_response_falls_back_to_model_key() -> None:
    data = {"models": [{"model": "llama3:8b"}]}
    assert parse_tags_response(data) == ["llama3:8b"]


def test_parse_ps_response_extracts_running_models() -> None:
    data = {"models": [{"name": "llama3:8b", "size": 123}]}
    assert parse_ps_response(data) == ["llama3:8b"]


def test_parse_ps_response_empty_means_nothing_running() -> None:
    assert parse_ps_response({"models": []}) == []
    assert parse_ps_response(None) == []


def test_systemctl_is_active_true(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="active\n", stderr="")

    monkeypatch.setattr("command_center.ollama.subprocess.run", fake_run)
    assert systemctl_is_active("ollama") is True


def test_systemctl_is_active_false(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 3, stdout="inactive\n", stderr="")

    monkeypatch.setattr("command_center.ollama.subprocess.run", fake_run)
    assert systemctl_is_active("ollama") is False


def test_systemctl_is_active_none_when_binary_missing(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("systemctl not found")

    monkeypatch.setattr("command_center.ollama.subprocess.run", fake_run)
    assert systemctl_is_active("ollama") is None


def test_systemctl_is_active_none_on_timeout(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="systemctl", timeout=2)

    monkeypatch.setattr("command_center.ollama.subprocess.run", fake_run)
    assert systemctl_is_active("ollama") is None


def test_get_status_offline_when_service_inactive(monkeypatch) -> None:
    monkeypatch.setattr("command_center.ollama.systemctl_is_active", lambda *a, **k: False)
    status = get_status()
    assert status.state == OllamaState.OFFLINE


def test_get_status_error_when_active_but_api_unreachable(monkeypatch) -> None:
    monkeypatch.setattr("command_center.ollama.systemctl_is_active", lambda *a, **k: True)
    monkeypatch.setattr("command_center.ollama._http_get_json", lambda *a, **k: None)
    status = get_status()
    assert status.state == OllamaState.ERROR


def test_get_status_offline_when_systemctl_unknown_and_api_unreachable(monkeypatch) -> None:
    monkeypatch.setattr("command_center.ollama.systemctl_is_active", lambda *a, **k: None)
    monkeypatch.setattr("command_center.ollama._http_get_json", lambda *a, **k: None)
    status = get_status()
    assert status.state == OllamaState.OFFLINE


def test_loaded_model_does_not_imply_busy(monkeypatch) -> None:
    """/api/ps only means a model is resident in memory, not generating."""
    responses = {
        "tags": {"models": [{"name": "llama3:8b"}]},
        "ps": {"models": [{"name": "llama3:8b"}]},
    }

    def fake_http(url, timeout):
        return responses["ps"] if url.endswith("/api/ps") else responses["tags"]

    monkeypatch.setattr("command_center.ollama.systemctl_is_active", lambda *a, **k: True)
    monkeypatch.setattr("command_center.ollama._http_get_json", fake_http)
    status = get_status()
    assert status.state == OllamaState.ONLINE
    assert status.state != OllamaState.BUSY
    assert status.current_model == "llama3:8b"


def test_get_status_idle_when_no_models_installed(monkeypatch) -> None:
    def fake_http(url, timeout):
        return {"models": []}

    monkeypatch.setattr("command_center.ollama.systemctl_is_active", lambda *a, **k: True)
    monkeypatch.setattr("command_center.ollama._http_get_json", fake_http)
    status = get_status()
    assert status.state == OllamaState.IDLE
    assert status.current_model == "-"


def test_get_status_online_when_ready_and_idle(monkeypatch) -> None:
    def fake_http(url, timeout):
        if url.endswith("/api/ps"):
            return {"models": []}
        return {"models": [{"name": "llama3:8b"}]}

    monkeypatch.setattr("command_center.ollama.systemctl_is_active", lambda *a, **k: True)
    monkeypatch.setattr("command_center.ollama._http_get_json", fake_http)
    status = get_status()
    assert status.state == OllamaState.ONLINE
    assert status.installed_models == ["llama3:8b"]


def test_get_status_unreachable_port_is_fast_and_safe() -> None:
    # No mocking here -- a real (very short timeout) call against a port
    # nothing is listening on, proving the dashboard never hangs waiting
    # on Ollama.
    status = get_status(host="127.0.0.1", port=1, timeout=0.3)
    assert status.state in (OllamaState.OFFLINE, OllamaState.ERROR)
