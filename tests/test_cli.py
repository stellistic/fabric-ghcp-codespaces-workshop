import json
from pathlib import Path

from workshop import cli

ROOT = Path(__file__).resolve().parents[1]


def test_offline_config_never_authenticates_or_calls_subprocess(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("an offline config check must not launch external tools")

    monkeypatch.setattr(cli.subprocess, "run", forbidden)
    assert cli.main(["config", "--config", str(ROOT / "demo.yaml")]) == 0
    assert json.loads(capsys.readouterr().out)["live_acceptance"] == "not evaluated"


def test_cli_reports_missing_approval_and_preserves_state(monkeypatch, tmp_path, capsys):
    state = tmp_path / "model.json"
    plan = tmp_path / "plan.json"
    from workshop.reporting import inject_fault, plan_repair

    inject_fault(ROOT / "data-model/model.json", state)
    plan.write_text(json.dumps(plan_repair(state)))
    before = state.read_bytes()
    monkeypatch.setattr(cli, "STATE", state)
    monkeypatch.setattr(cli, "PLAN", plan)
    assert cli.main(["report-repair", "--config", str(ROOT / "demo.yaml")]) == 2
    assert state.read_bytes() == before
    assert "approval" in capsys.readouterr().err
