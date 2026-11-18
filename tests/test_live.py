"""Offline Fabric contracts. Every subprocess is replaced; no authentication is performed."""

import base64
import json
import re
import shlex
import subprocess
import warnings
from dataclasses import replace
from pathlib import Path

import pytest
from nbformat import validate

from workshop import live
from workshop.config import Config, FabricConfig, SecurityConfig

TENANT = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
LAKEHOUSE = "33333333-3333-4333-8333-333333333333"
ITEM = "44444444-4444-4444-8444-444444444444"
OPERATION = "55555555-5555-4555-8555-555555555555"
JOB = "66666666-6666-4666-8666-666666666666"
BASE = f"workspaces/{WORKSPACE}"


def envelope(data):
    return {"status": "Success", "result": {"data": [data]}}


def response(body=None, status=200, headers=None):
    return envelope({"status_code": status, "headers": headers or {}, "text": body if body is not None else "(Empty)"})


def auth(**changes):
    return envelope({"logged_in": True, "tenant_id": TENANT, "token_fabric_powerbi": "NEVER-LOG"} | changes)


def preflight():
    return [
        auth(),
        response({"id": WORKSPACE, "displayName": "Workshop sandbox"}),
        response({"id": LAKEHOUSE, "workspaceId": WORKSPACE, "displayName": "plant", "type": "Lakehouse"}),
    ]


class FakeCLI:
    def __init__(self):
        self.replies = []
        self.calls = []
        self.definition = None

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        assert isinstance(argv, list) and argv[0] == "fab"
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["capture_output"] and kwargs["text"]
        assert 0 < kwargs["timeout"] <= 30
        assert not kwargs.get("shell", False)
        if "-i" in argv:
            body = json.loads(argv[argv.index("-i") + 1])
            if "definition" in body:
                self.definition = body["definition"]
        assert self.replies, f"Unexpected subprocess: {argv[:4]}"
        result = self.replies.pop(0)
        if isinstance(result, Exception):
            raise result
        if callable(result):
            result = result()
        if isinstance(result, subprocess.CompletedProcess):
            return result
        return subprocess.CompletedProcess(argv, 0, json.dumps(result), "diagnostic NEVER-LOG")


@pytest.fixture
def cli(monkeypatch, tmp_path):
    fake = FakeCLI()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(live.subprocess, "run", fake)
    monkeypatch.setattr(live.time, "sleep", lambda _: None)
    return fake


@pytest.fixture
def config():
    return Config(1, "synthetic-core", 20261001,
                  FabricConfig(TENANT, WORKSPACE, "Workshop sandbox", LAKEHOUSE, None, True),
                  SecurityConfig("synthetic-only", True, True))


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "repo"
    (path / "notebooks").mkdir(parents=True)
    notebook = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"dependencies": {"environment": {"id": "../hostile"}}},
        "cells": [
            {"cell_type": "code", "metadata": {"tags": ["parameters"]},
             "execution_count": None, "outputs": [],
             "source": ["expected_workspace_id = ''\nexpected_lakehouse_id = ''\n"
                        "sandbox = False\napproval = ''\nbatch_id = ''"]},
            {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
             "source": ["print('synthetic only')"]},
        ],
    }
    (path / "notebooks/02_bronze_ingest.ipynb").write_text(json.dumps(notebook))
    return path


def execute(config, root, action="preflight", **kwargs):
    return live.LiveAdapter(config, root=root, timeout=30).execute(action, **kwargs)


def notebook_item(cli):
    payload = json.loads(next(args[args.index("-i") + 1] for args in cli.calls
                              if "-i" in args and "definition" in json.loads(args[args.index("-i") + 1])))
    return {"id": ITEM, "workspaceId": WORKSPACE, "type": "Notebook",
            "displayName": payload["displayName"], "description": payload["description"]}


def publish(config, root, cli, asynchronous=False):
    cli.replies += preflight() + [response({"value": []})]
    if asynchronous:
        cli.replies += [
            response(status=202, headers={"Location": f"https://api.fabric.microsoft.com/v1/operations/{OPERATION}",
                                          "x-ms-operation-id": OPERATION, "Retry-After": "0"}),
            response({"status": "Running"}),
            response({"status": "Succeeded"}),
            lambda: response(notebook_item(cli)),
        ]
    else:
        cli.replies += [lambda: response(notebook_item(cli), 201)]
    return execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)


def state_file(root):
    return next((root / ".state/live").rglob("*.json"))


def owned_replies(cli):
    return [response(notebook_item(cli)), lambda: response({"definition": cli.definition})]


@pytest.mark.parametrize("fabric_changes,security_changes", [
    ({"tenant_id": None}, {}), ({"workspace_id": None}, {}), ({"workspace_name": None}, {}),
    ({"lakehouse_id": None}, {}), ({"tenant_id": "../tenant"}, {}), ({"workspace_id": WORKSPACE + " "}, {}),
    ({}, {"allow_live_read": False}), ({}, {"allow_live_read": "true"}),
])
def test_missing_identity_target_or_read_approval_never_spawns(config, root, cli, fabric_changes, security_changes):
    config = replace(config, fabric=replace(config.fabric, **fabric_changes),
                     security=replace(config.security, **security_changes))
    with pytest.raises(live.LiveError):
        execute(config, root)
    assert cli.calls == []


@pytest.mark.parametrize("change,approval", [
    ({}, None), ({}, TENANT), ({"sandbox": False}, WORKSPACE),
    ({"allow_live_write": False}, WORKSPACE), ({"approved_data": "approved-metadata"}, WORKSPACE),
])
@pytest.mark.parametrize("action", ["publish-notebook", "run-notebook"])
def test_write_gates_before_any_subprocess(config, root, cli, change, approval, action):
    if "sandbox" in change:
        config = replace(config, fabric=replace(config.fabric, **change))
    else:
        config = replace(config, security=replace(config.security, **change))
    with pytest.raises(live.LiveError):
        execute(config, root, action, notebook="bronze", participant="team01", approval=approval)
    assert cli.calls == []


@pytest.mark.parametrize("reply", [
    auth(logged_in=False), auth(tenant_id=WORKSPACE), auth(logged_in="true"),
    envelope({"tenant_id": TENANT}),
    {"status": "Failure", "result": {"message": "expired NEVER-LOG"}},
])
def test_auth_is_independent_and_fail_closed(config, root, cli, reply):
    cli.replies = [reply]
    with pytest.raises(live.LiveError):
        execute(config, root)
    assert len(cli.calls) == 1


@pytest.mark.parametrize("index,body", [
    (1, {"id": TENANT, "displayName": "Workshop sandbox"}),
    (1, {"id": WORKSPACE, "displayName": "other workspace"}),
    (2, {"id": LAKEHOUSE, "workspaceId": TENANT, "displayName": "plant"}),
    (2, {"id": LAKEHOUSE, "displayName": "plant"}),
])
def test_preflight_asserts_workspace_and_lakehouse(config, root, cli, index, body):
    cli.replies = preflight()
    cli.replies[index] = response(body)
    with pytest.raises(live.LiveError):
        execute(config, root)
    assert len(cli.calls) == index + 1


def test_verified_auth_wrapper_and_exact_uuid_endpoints(config, root, cli):
    cli.replies = preflight()
    result = execute(config, root)
    assert result["workspace_id"] == WORKSPACE
    assert cli.calls[0] == ["fab", "auth", "status", "--output_format", "json"]
    assert cli.calls[1][2] == BASE
    assert cli.calls[2][2] == f"{BASE}/lakehouses/{LAKEHOUSE}"
    assert "NEVER-LOG" not in json.dumps(result)


def test_inventory_pages_using_opaque_token_not_server_endpoint(config, root, cli):
    item = {"id": ITEM, "displayName": "User notebook", "type": "Notebook", "description": "NEVER-LOG"}
    cli.replies = preflight() + [
        response({"value": [item], "continuationToken": "opaque+/=="}),
        response({"value": [], "continuationToken": None}),
    ]
    result = execute(config, root, "inventory")
    assert len(result["items"]) == 1
    assert cli.calls[-1][2] == f"{BASE}/items"
    assert cli.calls[-1][cli.calls[-1].index("-P") + 1] == "continuationToken=opaque+/=="
    assert "NEVER-LOG" not in json.dumps(result)


@pytest.mark.parametrize("page", [
    {"value": [], "continuationToken": "x,attacker=value"},
    {"value": [], "continuationUri": "https://evil.example/steal"},
    {"value": [], "continuationToken": "x", "continuationUri": "https://api.fabric.microsoft.com.evil/v1/items"},
    {"value": [{"id": ITEM, "displayName": "../bad\nname", "type": "Notebook"}]},
    {"value": [{"id": "../path", "displayName": "test", "type": "Notebook"}]},
    {"value": [{"id": ITEM, "workspaceId": TENANT, "displayName": "test", "type": "Notebook"}]},
    {"value": "not-a-list"},
])
def test_inventory_rejects_hostile_or_malformed_pages(config, root, cli, page):
    cli.replies = preflight() + [response(page)]
    with pytest.raises(live.LiveError):
        execute(config, root, "inventory")
    assert len(cli.calls) == 4


def test_inventory_repeated_token_is_not_success(config, root, cli):
    page = response({"value": [], "continuationToken": "same"})
    cli.replies = preflight() + [page, page]
    with pytest.raises(live.LiveError, match="pagination"):
        execute(config, root, "inventory")
    assert len(cli.calls) == 5


@pytest.mark.parametrize("reply", [
    response({"message": "NEVER-LOG"}, 429, {"Retry-After": "90"}),
    response({"message": "NEVER-LOG"}, 403),
    subprocess.CompletedProcess(["fab"], 1, "NEVER-LOG", "NEVER-LOG"),
    subprocess.CompletedProcess(["fab"], 0, "not json NEVER-LOG", ""),
    subprocess.TimeoutExpired(["fab"], 30, output="NEVER-LOG"),
])
def test_transport_errors_are_bounded_and_do_not_leak(config, root, cli, reply):
    cli.replies = [reply] if not isinstance(reply, dict) else [auth(), reply]
    with pytest.raises(live.LiveError) as error:
        execute(config, root)
    assert "NEVER-LOG" not in str(error.value)
    assert len(cli.calls) <= 2


@pytest.mark.parametrize("notebook,participant", [
    ("../02_bronze_ingest", "team01"), ("recovery", "team01"), ("bronze", "../team"),
    ("bronze", "team;touch"), ("bronze", ""), ("bronze", "TEAM"),
])
def test_untrusted_notebook_or_participant_rejected_before_subprocess(config, root, cli, notebook, participant):
    with pytest.raises(live.LiveError):
        execute(config, root, "publish-notebook", notebook=notebook, participant=participant, approval=WORKSPACE)
    assert cli.calls == []


def test_symlink_notebook_is_not_publishable(config, root, cli):
    path = root / "notebooks/02_bronze_ingest.ipynb"
    original = path.read_text()
    path.unlink()
    (root / "outside.ipynb").write_text(original)
    path.symlink_to(root / "outside.ipynb")
    with pytest.raises(live.LiveError):
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert cli.calls == []


def test_publish_valid_definition_attachment_and_private_state(config, root, cli):
    result = publish(config, root, cli)
    assert result["item_id"] == ITEM and result["status"] == "Created"
    assert result["display_name"].startswith("ghcp_team01_bronze_")
    part, = cli.definition["parts"]
    assert cli.definition["format"] == "ipynb"
    assert part["path"] == "notebook-content.ipynb" and part["payloadType"] == "InlineBase64"
    notebook = json.loads(base64.b64decode(part["payload"]))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate(notebook)
    lh = notebook["metadata"]["dependencies"]["lakehouse"]
    assert lh["default_lakehouse"] == LAKEHOUSE
    assert lh["default_lakehouse_workspace_id"] == WORKSPACE
    assert lh["known_lakehouses"] == [{"id": LAKEHOUSE}]
    assert "environment" not in notebook["metadata"]["dependencies"]
    state = json.loads(state_file(root).read_text())
    assert state["item_id"] == ITEM and len(state["sha256"]) == 64
    assert state_file(root).stat().st_mode & 0o777 == 0o600
    assert "NEVER-LOG" not in json.dumps(state)


def test_existing_name_without_owned_state_is_never_overwritten(config, root, cli):
    publish(config, root, cli)
    item = notebook_item(cli)
    state_file(root).unlink()
    cli.calls.clear()
    cli.replies = preflight() + [response({"value": [item]})]
    with pytest.raises(live.LiveError, match="owned"):
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert not any("-i" in args for args in cli.calls)


def test_owned_matching_notebook_can_be_reused_but_never_updated(config, root, cli):
    publish(config, root, cli)
    cli.replies = preflight() + owned_replies(cli)
    result = execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert result["status"] == "Reused"
    assert sum("-i" in args and "definition" in json.loads(args[args.index("-i") + 1]) for args in cli.calls) == 1


@pytest.mark.parametrize("field,value", [
    ("tenant_id", WORKSPACE), ("workspace_id", TENANT), ("lakehouse_id", TENANT),
    ("sha256", "0" * 64), ("participant", "../other"), ("item_id", "../item"),
])
def test_state_mismatch_rejected_before_subprocess(config, root, cli, field, value):
    publish(config, root, cli)
    path = state_file(root)
    state = json.loads(path.read_text()) | {field: value}
    path.write_text(json.dumps(state))
    cli.calls.clear()
    with pytest.raises(live.LiveError, match="state"):
        execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert cli.calls == []


def test_remote_definition_drift_prevents_run(config, root, cli):
    publish(config, root, cli)
    altered = json.loads(base64.b64decode(cli.definition["parts"][0]["payload"]))
    altered["cells"][1]["source"] = ["print('changed')"]
    definition = {"format": "ipynb", "parts": [{
        "path": "notebook-content.ipynb", "payloadType": "InlineBase64",
        "payload": base64.b64encode(json.dumps(altered).encode()).decode(),
    }]}
    cli.replies = preflight() + [response(notebook_item(cli)), response({"definition": definition})]
    with pytest.raises(live.LiveError, match="drift"):
        execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert not any("/jobs/" in str(args) for args in cli.calls)


def test_create_lro_is_polled_and_result_id_persisted(config, root, cli):
    result = publish(config, root, cli, asynchronous=True)
    assert result["item_id"] == ITEM
    assert cli.calls[-1][2] == f"operations/{OPERATION}/result"
    assert json.loads(state_file(root).read_text())["operation_id"] == OPERATION


@pytest.mark.parametrize("headers", [
    {"Location": f"https://evil.example/v1/operations/{OPERATION}"},
    {"Location": f"https://api.fabric.microsoft.com@evil.example/v1/operations/{OPERATION}"},
    {"Location": f"https://api.fabric.microsoft.com/v1/operations/{OPERATION}?token=bad"},
    {"x-ms-operation-id": "../bad"},
    {},
])
def test_create_lro_does_not_follow_untrusted_location(config, root, cli, headers):
    cli.replies = preflight() + [response({"value": []}), response(status=202, headers=headers)]
    with pytest.raises(live.LiveError):
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert len(cli.calls) == 5
    assert json.loads(state_file(root).read_text())["phase"] != "created"


def test_lro_timeout_preserves_operation_and_read_only_resume(config, root, cli, monkeypatch):
    cli.replies = preflight() + [response({"value": []}),
                                response(status=202, headers={"x-ms-operation-id": OPERATION, "Retry-After": "900"})]
    with pytest.raises(live.LiveError, match="timeout"):
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert json.loads(state_file(root).read_text())["operation_id"] == OPERATION
    after_delay = live.time.time() + 901
    monkeypatch.setattr(live.time, "time", lambda: after_delay)
    config = replace(config, security=replace(config.security, allow_live_write=False))
    cli.replies = preflight() + [response({"status": "Succeeded"}), lambda: response(notebook_item(cli))]
    result = execute(config, root, "get-results", notebook="bronze", participant="team01")
    assert result["item_id"] == ITEM
    assert not any("-X" in args and args[args.index("-X") + 1] != "get" for args in cli.calls[-5:])


def test_run_bounded_poll_and_read_only_results(config, root, cli):
    publish(config, root, cli)
    location = f"https://api.fabric.microsoft.com/v1/{BASE}/items/{ITEM}/jobs/instances/{JOB}"
    cli.replies = preflight() + owned_replies(cli) + [
        response(status=202, headers={"Location": location, "Retry-After": "0"}),
        response({"id": JOB, "itemId": ITEM, "status": "InProgress"}),
        response({"id": JOB, "itemId": ITEM, "status": "Completed", "exitValue": "synthetic summary"}),
    ]
    result = execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert result["status"] == "Completed" and result["job_id"] == JOB
    run = next(args for args in cli.calls if "/jobs/RunNotebook/instances" in str(args))
    body = json.loads(run[run.index("-i") + 1])
    assert set(body["executionData"]["parameters"]) == {
        "expected_workspace_id", "expected_lakehouse_id", "sandbox", "approval", "batch_id",
    }
    assert body["executionData"]["parameters"]["expected_workspace_id"]["value"] == WORKSPACE
    assert body["executionData"]["parameters"]["expected_lakehouse_id"]["value"] == LAKEHOUSE
    assert body["executionData"]["parameters"]["sandbox"] == {"type": "bool", "value": True}
    assert body["executionData"]["parameters"]["approval"]["value"] == WORKSPACE
    assert json.loads(state_file(root).read_text())["job_id"] == JOB
    config = replace(config, security=replace(config.security, allow_live_write=False))
    cli.replies = preflight() + [response({"id": JOB, "itemId": ITEM, "status": "Completed", "exitValue": "summary"})]
    result = execute(config, root, "get-results", notebook="bronze", participant="team01")
    assert result["status"] == "Completed"
    assert "exitValue" not in result
    saved = root / result["results_file"]
    assert json.loads(saved.read_text())["exitValue"] == "summary"
    assert saved.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("status", ["Failed", "Cancelled", "unexpected"])
def test_run_never_claims_success_for_failed_or_unknown_job(config, root, cli, status):
    publish(config, root, cli)
    location = f"https://api.fabric.microsoft.com/v1/{BASE}/items/{ITEM}/jobs/instances/{JOB}"
    cli.replies = preflight() + owned_replies(cli) + [
        response(status=202, headers={"Location": location, "Retry-After": "0"}),
        response({"id": JOB, "itemId": ITEM, "status": status, "failureReason": "NEVER-LOG"}),
    ]
    with pytest.raises(live.LiveError):
        execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)


def test_cli_default_config_and_help_never_spawn(cli, capsys):
    assert live.main(["--help"]) == 0
    assert "publish-notebook" in capsys.readouterr().out
    assert live.main(["--config", "missing.local.yaml", "preflight"]) == 1
    assert cli.calls == []


def test_cli_uses_strict_complete_config(cli, root, capsys):
    path = root / "demo.local.yaml"
    path.write_text("fabric:\n  workspace_id: anything\n")
    assert live.main(["--config", str(path), "inventory"]) == 1
    assert cli.calls == []
    assert "NEVER-LOG" not in capsys.readouterr().err


@pytest.mark.parametrize("key", ["debug_enabled", "encryption_fallback_enabled"])
def test_unsafe_cli_settings_are_rejected_without_subprocess(config, root, cli, key):
    path = Path.home() / ".config/fab/config.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({key: "true"}))
    with pytest.raises(live.LiveError, match="debug logging"):
        execute(config, root)
    assert cli.calls == []


def test_create_lro_failure_preserves_state_and_does_not_claim_creation(config, root, cli):
    cli.replies = preflight() + [
        response({"value": []}), response(status=202, headers={"x-ms-operation-id": OPERATION, "Retry-After": "0"}),
        response({"status": "Failed", "error": {"message": "NEVER-LOG"}}),
    ]
    with pytest.raises(live.LiveError, match="operation failed") as error:
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert "NEVER-LOG" not in str(error.value)
    state = json.loads(state_file(root).read_text())
    assert state["operation_id"] == OPERATION and "item_id" not in state


def test_unacknowledged_create_is_not_resubmitted(config, root, cli):
    cli.replies = preflight() + [
        response({"value": []}), subprocess.TimeoutExpired(["fab"], 30),
    ]
    with pytest.raises(live.LiveError, match="timeout"):
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert json.loads(state_file(root).read_text())["phase"] == "submitting"
    cli.replies = preflight()
    with pytest.raises(live.LiveError, match="unresolved"):
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert len([args for args in cli.calls if "-i" in args]) == 1


def test_job_timeout_records_id_and_does_not_cancel_or_resubmit(config, root, cli):
    publish(config, root, cli)
    location = f"https://api.fabric.microsoft.com/v1/{BASE}/items/{ITEM}/jobs/instances/{JOB}"
    cli.replies = preflight() + owned_replies(cli) + [
        response(status=202, headers={"Location": location, "Retry-After": "900"}),
    ]
    with pytest.raises(live.LiveError, match="timeout"):
        execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert json.loads(state_file(root).read_text())["job_id"] == JOB
    assert not any("cancel" in str(args) for args in cli.calls)
    cli.replies = preflight()
    with pytest.raises(live.LiveError, match="unresolved"):
        execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert len([args for args in cli.calls if "/jobs/RunNotebook/instances" in str(args)]) == 1


def test_resuming_creation_respects_persisted_retry_after(config, root, cli):
    cli.replies = preflight() + [
        response({"value": []}), response(status=202, headers={"x-ms-operation-id": OPERATION, "Retry-After": "900"}),
    ]
    with pytest.raises(live.LiveError, match="timeout"):
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    state = json.loads(state_file(root).read_text())
    assert state["poll_after"] >= live.time.time() + 898
    cli.replies = preflight()
    before = len(cli.calls)
    with pytest.raises(live.LiveError, match="timeout"):
        execute(config, root, "get-results", notebook="bronze", participant="team01")
    assert len(cli.calls) == before + 3


@pytest.mark.parametrize("location", [
    f"https://evil.example/v1/{BASE}/items/{ITEM}/jobs/instances/{JOB}",
    f"https://api.fabric.microsoft.com/v1/{BASE}/items/{TENANT}/jobs/instances/{JOB}",
    f"https://api.fabric.microsoft.com/v1/{BASE}/items/{ITEM}/jobs/instances/{JOB}?token=x",
    "https://[invalid",
])
def test_job_location_cannot_escape_recorded_item(config, root, cli, location):
    publish(config, root, cli)
    cli.replies = preflight() + owned_replies(cli) + [response(status=202, headers={"Location": location})]
    with pytest.raises(live.LiveError):
        execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert json.loads(state_file(root).read_text())["phase"] == "run-submitting"


def test_malformed_state_cannot_crash_or_trigger_live_calls(config, root, cli):
    publish(config, root, cli)
    path = state_file(root)
    state = json.loads(path.read_text())
    state.pop("item_id")
    path.write_text(json.dumps(state))
    cli.calls.clear()
    with pytest.raises(live.LiveError, match="state"):
        execute(config, root, "get-results", notebook="bronze", participant="team01")
    assert cli.calls == []


def test_approved_metadata_results_never_save_notebook_exit_content(config, root, cli):
    publish(config, root, cli)
    path = state_file(root)
    state = json.loads(path.read_text()) | {"job_id": JOB, "job_status": "Completed"}
    path.write_text(json.dumps(state))
    config = replace(config, security=SecurityConfig("approved-metadata", True, False))
    cli.replies = preflight() + [
        response({"id": JOB, "itemId": ITEM, "status": "Completed", "exitValue": "NEVER-LOG"}),
    ]
    result = execute(config, root, "get-results", notebook="bronze", participant="team01")
    saved = (root / result["results_file"]).read_text()
    assert "NEVER-LOG" not in saved and "exitValue" not in saved
    assert "NEVER-LOG" not in json.dumps(result)


def test_results_without_a_job_verify_live_item_and_do_not_claim_run_success(config, root, cli):
    publish(config, root, cli)
    cli.replies = preflight() + [response(notebook_item(cli))]
    result = execute(config, root, "get-results", notebook="bronze", participant="team01")
    assert result["status"] == "NotRun" and result["item_id"] == ITEM
    assert cli.calls[-1][2] == f"{BASE}/items/{ITEM}"
    cli.replies = preflight() + [response(status=404)]
    with pytest.raises(live.LiveError, match="404"):
        execute(config, root, "get-results", notebook="bronze", participant="team01")


def test_definition_path_is_not_interpreted_as_a_local_or_remote_resource(config, root, cli):
    publish(config, root, cli)
    definition = {"parts": [{"path": "../../hostile.ipynb", "payload": "ignored", "payloadType": "InlineBase64"}]}
    cli.replies = preflight() + [response(notebook_item(cli)), response({"definition": definition})]
    with pytest.raises(live.LiveError, match="definition path"):
        execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert not any("/jobs/" in str(args) for args in cli.calls)


@pytest.mark.parametrize("source", [
    "sandbox = True", "expected_workspace_id = 'implicit-target'",
    "import os\nsandbox = False", "expected_workspace_id = input()",
])
def test_missing_or_unsafe_guard_parameter_defaults_rejected_locally(config, root, cli, source):
    path = root / "notebooks/02_bronze_ingest.ipynb"
    notebook = json.loads(path.read_text())
    notebook["cells"][0]["source"] = source
    path.write_text(json.dumps(notebook))
    with pytest.raises(live.LiveError, match="parameter"):
        execute(config, root, "publish-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    assert cli.calls == []


def test_previous_explicit_uuid_parameter_contract_is_supported_without_implicit_targets(config, root, cli):
    path = root / "notebooks/02_bronze_ingest.ipynb"
    notebook = json.loads(path.read_text())
    notebook["cells"][0]["source"] = (
        "workspace_id = ''\nlakehouse_id = ''\nsandbox = False\napproval = ''\nbatch_id = ''"
    )
    path.write_text(json.dumps(notebook))
    publish(config, root, cli)
    location = f"https://api.fabric.microsoft.com/v1/{BASE}/items/{ITEM}/jobs/instances/{JOB}"
    cli.replies = preflight() + owned_replies(cli) + [
        response(status=202, headers={"Location": location, "Retry-After": "0"}),
        response({"id": JOB, "itemId": ITEM, "status": "Completed"}),
    ]
    execute(config, root, "run-notebook", notebook="bronze", participant="team01", approval=WORKSPACE)
    run = next(args for args in cli.calls if "/jobs/RunNotebook/instances" in str(args))
    parameters = json.loads(run[run.index("-i") + 1])["executionData"]["parameters"]
    assert parameters["workspace_id"]["value"] == WORKSPACE
    assert parameters["lakehouse_id"]["value"] == LAKEHOUSE
    assert "expected_workspace_id" not in parameters


@pytest.mark.parametrize("choice", ["bronze", "silver", "silver-dims", "gold"])
def test_actual_repository_notebooks_stage_offline_with_valid_guard_contract(config, cli, choice):
    adapter = live.LiveAdapter(config)
    expected = adapter._prepare(choice, "offline-contract")
    workspace_parameter, lakehouse_parameter = adapter._parameter_names(expected["content"])
    assert workspace_parameter in ("workspace_id", "expected_workspace_id")
    assert lakehouse_parameter in ("lakehouse_id", "expected_lakehouse_id")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate(expected["content"])
    assert cli.calls == []


def test_devcontainer_lifecycle_references_existing_non_world_writable_scripts():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / ".devcontainer/devcontainer.json").read_text())
    assert config["build"]["context"] == "."
    assert (root / ".devcontainer" / config["build"]["dockerfile"]).is_file()
    argv = shlex.split(config["postCreateCommand"])
    assert argv[0] == "bash"
    for relative in (argv[1], ".devcontainer/fabric-terminal.sh"):
        script = root / relative
        assert script.is_file() and not script.is_symlink()
        assert script.stat().st_mode & 0o002 == 0
        assert script.read_text().startswith("#!/usr/bin/env bash\nset -euo pipefail")
    setup = (root / argv[1]).read_text()
    assert setup.index("uv sync --frozen") < setup.index("npm ci --ignore-scripts")
    commands = "\n".join(line for line in setup.splitlines() if not line.startswith("#"))
    assert "auth login" not in commands and "auth status" not in commands and "workshop.live --help" in commands
    assert re.search(r'"version":\s*"2[2-9]\.', json.dumps(config["features"]))


def test_copilot_lock_is_complete_and_public_registry_only():
    root = Path(__file__).resolve().parents[1]
    package = json.loads((root / "package.json").read_text())
    lock = json.loads((root / "package-lock.json").read_text())
    packages = lock["packages"]
    assert package["private"] is True
    assert packages[""]["devDependencies"] == package["devDependencies"]
    copilot = packages["node_modules/@github/copilot"]
    assert copilot["version"] == package["devDependencies"]["@github/copilot"]
    for name, version in copilot.get("optionalDependencies", {}).items():
        assert packages[f"node_modules/{name}"]["version"] == version
    for name, entry in packages.items():
        if name:
            assert entry["resolved"].startswith("https://registry.npmjs.org/")
            assert entry["integrity"].startswith("sha512-")
