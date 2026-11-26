"""Deployment gates and recovery are exercised without touching the live service."""

from unittest.mock import Mock, call

import pytest

from scripts import deploy_vultr as deploy


OLD = "a" * 40
NEW = "b" * 40
SUCCESSFUL_RUN = {
    "head_sha": NEW, "head_branch": "main", "event": "push",
    "status": "completed", "conclusion": "success",
}


@pytest.fixture
def host(monkeypatch, tmp_path):
    commands = Mock()
    restart = Mock()
    monkeypatch.setattr(deploy, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(deploy, "git", commands)
    monkeypatch.setattr(deploy, "restart_and_wait", restart)
    return commands, restart


@pytest.mark.parametrize("change", [
    {"head_sha": OLD}, {"head_branch": "test"}, {"event": "pull_request"},
    {"status": "in_progress"}, {"conclusion": "failure"}, {"conclusion": "cancelled"},
])
def test_only_the_exact_successful_main_push_passes(change):
    assert deploy.matches_run(SUCCESSFUL_RUN, NEW)
    assert not deploy.matches_run({**SUCCESSFUL_RUN, **change}, NEW)


def test_pending_ci_leaves_the_running_checkout_alone(host, monkeypatch):
    commands, restart = host
    commands.side_effect = ["", OLD, None, NEW]
    ci = Mock(return_value=False)
    monkeypatch.setattr(deploy, "passed_main_ci", ci)

    deploy.deploy()

    ci.assert_called_once_with(NEW)
    restart.assert_not_called()
    assert call("switch", "--detach", NEW) not in commands.mock_calls
    assert not deploy.STATE_PATH.exists()


def test_rollout_records_recovery_before_switch_and_clears_it_when_healthy(host):
    commands, restart = host
    release = deploy.Release(OLD, NEW)

    def verify_pending():
        assert deploy.read_state() == {"pending": {"previous": OLD, "target": NEW}}

    restart.side_effect = verify_pending
    deploy.activate(release, {})

    commands.assert_called_once_with("switch", "--detach", NEW)
    restart.assert_called_once()
    assert deploy.read_state() == {}


def test_unhealthy_release_restores_previous_and_is_not_retried(host):
    commands, restart = host
    restart.side_effect = [RuntimeError("Unhealthy candidate"), None]

    with pytest.raises(RuntimeError, match="Unhealthy candidate"):
        deploy.activate(deploy.Release(OLD, NEW), {})

    assert commands.mock_calls == [call("switch", "--detach", NEW), call("switch", "--detach", OLD)]
    assert restart.call_count == 2
    assert deploy.read_state() == {"rejected": NEW}
    commands.side_effect = [OLD, None, NEW]
    assert deploy.candidate(deploy.read_state()) is None


def test_interruption_recovers_from_the_persisted_release(host):
    commands, restart = host
    commands.return_value = ""
    deploy.write_state({"pending": {"previous": OLD, "target": NEW}})

    deploy.deploy()

    assert commands.mock_calls == [
        call("status", "--porcelain", "--untracked-files=no", capture=True),
        call("switch", "--detach", OLD),
    ]
    restart.assert_called_once()
    assert deploy.read_state() == {"rejected": NEW}


def test_failed_rollback_leaves_recovery_available_for_next_run(host):
    _, restart = host
    restart.side_effect = RuntimeError("Not ready")

    with pytest.raises(RuntimeError, match="Not ready"):
        deploy.activate(deploy.Release(OLD, NEW), {})

    assert deploy.read_state() == {"pending": {"previous": OLD, "target": NEW}}


def test_dependency_changes_leave_the_rollback_runtime_available(host):
    commands, restart = host
    commands.side_effect = [None, "backend/requirements.txt"]

    with pytest.raises(RuntimeError, match="Python requirements changed"):
        deploy.verify_runtime(deploy.Release(OLD, NEW))

    restart.assert_not_called()


@pytest.mark.parametrize("response", [
    None, {"ok": True, "service": "semantic-product-search", "status": "initializing"},
    {"ok": True, "service": "other-api", "status": "ready"},
])
def test_only_the_ready_backend_passes_health(response):
    assert not deploy.is_ready_response(response)
    assert deploy.is_ready_response({"ok": True, "service": "semantic-product-search", "status": "ready"})
