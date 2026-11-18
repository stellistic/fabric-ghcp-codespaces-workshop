"""Opt-in, bounded Fabric notebook adapter. Importing this module never contacts Fabric."""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from workshop.config import Config, load_config

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = {
    "bronze": "02_bronze_ingest.ipynb",
    "silver": "03_silver_transform.ipynb",
    "silver-dims": "04_silver_dims_catchup.ipynb",
    "gold": "05_gold_star_schema.ipynb",
}
ACTIONS = ("preflight", "inventory", "publish-notebook", "run-notebook", "get-results")
MAX_BYTES = 8 * 1024 * 1024
JOB_STATUSES = {"NotStarted", "InProgress", "Completed", "Failed", "Cancelled", "Deduped"}


class LiveError(Exception):
    """Safe diagnostic: never includes subprocess output, credentials, or remote errors."""


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise LiveError("expected an explicit canonical UUID")
    try:
        parsed = UUID(value)
    except ValueError:
        raise LiveError("expected an explicit canonical UUID") from None
    if str(parsed) != value or not parsed.int:
        raise LiveError("expected a nonzero canonical UUID")
    return value


def _object(value: object) -> dict:
    if not isinstance(value, dict):
        raise LiveError("malformed Fabric response")
    return value


def _text(value: object, limit: int = 256) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not value.isprintable():
        raise LiveError("invalid Fabric metadata")
    return value


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _location(value: object, expected: str) -> str:
    """Only convert an exact Fabric v1 resource URL into an internally generated route."""
    if not isinstance(value, str):
        raise LiveError("missing Fabric operation location")
    parsed = _url(value)
    if (parsed.scheme != "https" or parsed.netloc != "api.fabric.microsoft.com"
            or parsed.query or parsed.fragment or parsed.path != f"/v1/{expected}"):
        raise LiveError("untrusted Fabric operation location")
    return expected


def _url(value: str):
    try:
        return urlsplit(value)
    except ValueError:
        raise LiveError("invalid Fabric resource URL") from None


def _secure_cli_settings() -> None:
    """Read settings, never credential caches; refuse CLI debug/plaintext-cache logging risks."""
    path = Path.home() / ".config/fab/config.json"
    try:
        if not path.exists():
            return
        if path.stat().st_size > 65536:
            raise LiveError("Fabric CLI settings rejected")
        settings = _object(json.loads(path.read_text(encoding="utf-8")))
        for key in ("debug_enabled", "encryption_fallback_enabled"):
            if settings.get(key, "false") != "false":
                raise LiveError("disable Fabric CLI debug logging and plaintext encryption fallback before live use")
    except (OSError, ValueError):
        raise LiveError("cannot verify secure Fabric CLI settings") from None


@dataclass(frozen=True)
class Response:
    body: dict
    status: int
    headers: dict


class LiveAdapter:
    def __init__(self, config: Config, *, root: Path = ROOT, timeout: int = 300):
        self.config = config
        self.root = root.resolve()
        if type(timeout) is not int or not 1 <= timeout <= 1800:
            raise LiveError("timeout must be between 1 and 1800 seconds")
        self.timeout = timeout
        self.deadline = 0.0
        self.requests = 0
        self.workspace = config.fabric.workspace_id
        self.base = f"workspaces/{self.workspace}"

    def _guard(self, action: str, approval: str | None) -> None:
        cfg = self.config
        if action not in ACTIONS:
            raise LiveError("unsupported action")
        if cfg.version != 1 or cfg.profile != "synthetic-core" or cfg.seed != 20261001:
            raise LiveError("unsupported workshop configuration")
        for value in (cfg.fabric.tenant_id, self.workspace, cfg.fabric.lakehouse_id):
            _uuid(value)
        if not isinstance(cfg.fabric.workspace_name, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 _-]{0,99}", cfg.fabric.workspace_name
        ):
            raise LiveError("an explicit workspace name is required")
        if cfg.security.allow_live_read is not True:
            raise LiveError("explicit live read approval is required")
        if cfg.security.approved_data not in ("synthetic-only", "approved-metadata"):
            raise LiveError("unsupported data approval")
        if action in ("publish-notebook", "run-notebook") and not (
            cfg.fabric.sandbox is True
            and cfg.security.allow_live_write is True
            and cfg.security.approved_data == "synthetic-only"
            and approval == self.workspace
        ):
            raise LiveError("writes require a synthetic sandbox, write approval and --approve-workspace EXACT_UUID")

    def _remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise LiveError("timeout; remote work may still be running; inspect state and use get-results")
        return remaining

    def _cli(self, args: list[str]) -> dict:
        _secure_cli_settings()
        self.requests += 1
        if self.requests > 256:
            raise LiveError("request bound exceeded; remote work may still be running")
        try:
            result = subprocess.run(
                ["fab", *args, "--output_format", "json"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=min(30, self._remaining()), check=False,
            )
        except subprocess.TimeoutExpired:
            raise LiveError("subprocess timeout; remote work may still be running; inspect state") from None
        except OSError:
            raise LiveError("Fabric CLI unavailable; install the pinned development tools") from None
        if result.returncode:
            raise LiveError("Fabric CLI failed; verify login and permissions manually (raw output suppressed)")
        try:
            if len(result.stdout) > MAX_BYTES:
                raise LiveError("Fabric response exceeds size bound")
            output = _object(json.loads(result.stdout))
            data = _object(output.get("result")).get("data")
            if output.get("status") != "Success" or not isinstance(data, list) or len(data) != 1:
                raise LiveError("Fabric CLI returned failure or an unsupported envelope")
            return _object(data[0])
        except (ValueError, TypeError):
            raise LiveError("Fabric CLI returned invalid JSON (raw output suppressed)") from None

    def _api(self, route: str, *, method: str = "get", body: dict | None = None,
             token: str | None = None) -> Response:
        # Routes originate exclusively from validated UUIDs and fixed strings in this module.
        if method not in ("get", "post") or not route.startswith((self.base, "operations/")):
            raise LiveError("unsupported internal route")
        args = ["api", route, "-X", method, "--show_headers"]
        if body is not None:
            args += ["-i", _encoded(body).decode("utf-8")]
        if token is not None:
            args += ["-P", f"continuationToken={token}"]
        result = self._cli(args)
        status = result.get("status_code")
        if type(status) is not int:
            raise LiveError("missing HTTP status in Fabric response")
        headers = _object(result.get("headers"))
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
            raise LiveError("invalid Fabric response headers")
        headers = {key.lower(): value for key, value in headers.items()}
        if status == 429:
            raise LiveError("Fabric rate limit (429); no automatic retry; wait before retrying manually")
        if status not in (200, 201, 202):
            raise LiveError(f"Fabric HTTP {status}; no changes retried (raw output suppressed)")
        text = result.get("text")
        body = {} if text == "(Empty)" or text is None else _object(text)
        return Response(body, status, headers)

    @staticmethod
    def _ok(response: Response, status: int = 200) -> dict:
        if response.status != status:
            raise LiveError("unexpected HTTP status; operation is not confirmed complete")
        return response.body

    def _preflight(self) -> dict:
        auth = self._cli(["auth", "status"])
        if auth.get("logged_in") is not True or auth.get("tenant_id") != self.config.fabric.tenant_id:
            raise LiveError("authentication expired, missing, or tenant mismatch; log in manually to selected tenant")
        workspace = self._ok(self._api(self.base))
        if workspace.get("id") != self.workspace or workspace.get("displayName") != self.config.fabric.workspace_name:
            raise LiveError("workspace UUID/name mismatch")
        lakehouse = self._ok(self._api(f"{self.base}/lakehouses/{self.config.fabric.lakehouse_id}"))
        if lakehouse.get("id") != self.config.fabric.lakehouse_id or lakehouse.get("workspaceId") != self.workspace:
            raise LiveError("lakehouse does not belong to the selected workspace")
        self.lakehouse_name = _text(lakehouse.get("displayName"))
        return {"status": "Verified", "tenant_id": self.config.fabric.tenant_id,
                "workspace_id": self.workspace, "lakehouse_id": self.config.fabric.lakehouse_id}

    def _inventory(self) -> list[dict]:
        items = []
        token = None
        seen = set()
        route = f"{self.base}/items"
        for _ in range(100):
            page = self._ok(self._api(route, token=token))
            values = page.get("value")
            if not isinstance(values, list) or len(items) + len(values) > 10000:
                raise LiveError("invalid or oversized inventory page")
            for value in values:
                item = _object(value)
                item_id = _uuid(item.get("id"))
                name = _text(item.get("displayName"))
                item_type = _text(item.get("type"), 64)
                if any(c in name for c in "/\\") or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", item_type):
                    raise LiveError("invalid Fabric inventory metadata")
                if item.get("workspaceId", self.workspace) != self.workspace:
                    raise LiveError("inventory workspace mismatch")
                items.append({"id": item_id, "displayName": name, "type": item_type})
            token = page.get("continuationToken")
            uri = page.get("continuationUri")
            if uri is not None:
                if not isinstance(uri, str):
                    raise LiveError("invalid pagination URI")
                parsed = _url(uri)
                if (parsed.scheme != "https" or parsed.netloc != "api.fabric.microsoft.com"
                        or parsed.path != f"/v1/{route}" or parsed.fragment
                        or parse_qs(parsed.query) != {"continuationToken": [token]}):
                    raise LiveError("untrusted pagination URI")
            if token is None:
                return items
            if (not isinstance(token, str) or not 1 <= len(token) <= 4096
                    or not token.isprintable() or "," in token or token in seen):
                raise LiveError("unsafe or repeated pagination token")
            seen.add(token)
        raise LiveError("pagination limit exceeded; inventory incomplete")

    def _path(self, relative: str) -> Path:
        path = self.root / relative
        if not path.is_relative_to(self.root) or ".." in path.parts:
            raise LiveError("unsafe local path")
        current = self.root
        for part in path.relative_to(self.root).parts:
            current /= part
            if current.is_symlink():
                raise LiveError("symlinks are not allowed for notebook, state or results paths")
        return path

    @staticmethod
    def _notebook(value: object) -> dict:
        nb = _object(value)
        if nb.get("nbformat") != 4 or not isinstance(nb.get("cells"), list) or not 1 <= len(nb["cells"]) <= 500:
            raise LiveError("invalid notebook")
        cells = []
        for index, cell_value in enumerate(nb["cells"]):
            cell = _object(cell_value)
            kind = cell.get("cell_type")
            source = cell.get("source")
            if kind not in ("code", "markdown") or not (
                isinstance(source, str) or isinstance(source, list) and all(isinstance(s, str) for s in source)
            ):
                raise LiveError("invalid notebook cell")
            source = "".join(source) if isinstance(source, list) else source
            tags = _object(cell.get("metadata", {})).get("tags", [])
            cell_id = _digest([index, kind, source])[:16]
            clean = {"id": cell_id, "cell_type": kind, "source": source, "metadata": {}}
            if kind == "code":
                clean.update({"execution_count": None, "outputs": []})
                if isinstance(tags, list) and "parameters" in tags:
                    clean["metadata"] = {"tags": ["parameters"]}
            cells.append(clean)
        if sum(c["metadata"].get("tags") == ["parameters"] for c in cells) != 1:
            raise LiveError("notebook must contain exactly one parameters cell")
        metadata = _object(nb.get("metadata", {}))
        return {"nbformat": 4, "nbformat_minor": 5, "cells": cells, "metadata": metadata}

    def _prepare(self, notebook: str | None, participant: str | None) -> dict:
        if notebook not in NOTEBOOKS or not isinstance(participant, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9_-]{0,23}", participant
        ):
            raise LiveError("select an allowlisted notebook and a lowercase participant slug (1-24 characters)")
        path = self._path(f"notebooks/{NOTEBOOKS[notebook]}")
        try:
            if path.stat().st_size > MAX_BYTES:
                raise LiveError("notebook exceeds size bound")
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise LiveError("cannot read the fixed repository notebook; build and review it first") from None
        nb = self._notebook(value)
        self._parameter_names(nb)
        nb["metadata"] = {
            "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
            "language_info": {"name": "python"},
            "dependencies": {"lakehouse": {
                "default_lakehouse": self.config.fabric.lakehouse_id,
                "default_lakehouse_workspace_id": self.workspace,
                "known_lakehouses": [{"id": self.config.fabric.lakehouse_id}],
            }},
        }
        digest = _digest(nb)
        name = f"ghcp_{participant}_{notebook.replace('-', '_')}_{digest[:12]}"
        return {"version": 1, "tenant_id": self.config.fabric.tenant_id, "workspace_id": self.workspace,
                "lakehouse_id": self.config.fabric.lakehouse_id, "notebook": notebook, "participant": participant,
                "display_name": name, "sha256": digest, "content": nb}

    @staticmethod
    def _parameter_names(notebook: dict) -> tuple[str, str]:
        cell = next(cell for cell in notebook["cells"] if cell["metadata"].get("tags") == ["parameters"])
        try:
            declarations = ast.parse(cell["source"]).body
            defaults = {}
            for declaration in declarations:
                if (not isinstance(declaration, ast.Assign) or len(declaration.targets) != 1
                        or not isinstance(declaration.targets[0], ast.Name)):
                    raise ValueError
                name = declaration.targets[0].id
                if name in defaults:
                    raise ValueError
                defaults[name] = ast.literal_eval(declaration.value)
            for workspace_name, lakehouse_name in (
                ("expected_workspace_id", "expected_lakehouse_id"), ("workspace_id", "lakehouse_id"),
            ):
                required = {workspace_name: "", lakehouse_name: "", "sandbox": False, "approval": "", "batch_id": ""}
                if defaults == required and defaults["sandbox"] is False:
                    return workspace_name, lakehouse_name
        except (ValueError, SyntaxError, TypeError):
            pass
        raise LiveError("notebook guard parameters must have the complete fail-closed literal defaults")

    def _state_path(self, expected: dict) -> Path:
        return self._path(f".state/live/{self.workspace}/{expected['display_name']}.json")

    def _load_state(self, expected: dict) -> dict | None:
        path = self._state_path(expected)
        if not path.exists():
            return None
        try:
            if path.stat().st_size > 65536:
                raise LiveError("invalid state size")
            state = _object(json.loads(path.read_text(encoding="utf-8")))
            allowed = (set(expected) - {"content"}) | {
                "phase", "item_id", "operation_id", "job_id", "job_status", "poll_after",
            }
            if not set(state) <= allowed:
                raise LiveError("unexpected state fields")
            if any(state.get(key) != value for key, value in expected.items() if key != "content"):
                raise LiveError("state identity or notebook hash mismatch")
            for key in ("item_id", "operation_id", "job_id"):
                if key in state:
                    _uuid(state[key])
            phase = state.get("phase")
            if phase not in ("submitting", "accepted", "created", "create-failed", "run-submitting"):
                raise LiveError("invalid state phase")
            if phase == "accepted" and "operation_id" not in state:
                raise LiveError("missing state operation ID")
            if phase in ("created", "run-submitting") and "item_id" not in state:
                raise LiveError("missing state item ID")
            if "job_id" in state and "job_status" not in state:
                raise LiveError("missing state job status")
            if "job_status" in state and (
                not isinstance(state["job_status"], str) or state["job_status"] not in JOB_STATUSES
            ):
                raise LiveError("invalid state job status")
            if "poll_after" in state and (
                type(state["poll_after"]) not in (int, float)
                or not math.isfinite(state["poll_after"]) or not 0 <= state["poll_after"] <= 2**53
            ):
                raise LiveError("invalid state polling deadline")
            return state
        except (ValueError, OSError, LiveError):
            raise LiveError("state rejected; preserve it and reconcile exact IDs manually") from None

    def _write(self, path: Path, value: dict) -> None:
        relative = str(path.relative_to(self.root))
        self._path(relative)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        pending = self._path(relative + ".new")
        try:
            descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(value, sort_keys=True, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._path(relative)
            os.replace(pending, path)
        except OSError:
            raise LiveError("cannot safely persist state/results; stop and inspect local files") from None

    @contextmanager
    def _lock(self, expected: dict):
        path = self._state_path(expected)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock = self._path(str(path.relative_to(self.root)) + ".lock")
        try:
            descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            raise LiveError("state is locked; do not retry until prior work has stopped and been reconciled") from None
        try:
            os.close(descriptor)
            yield
        finally:
            lock.unlink()

    @staticmethod
    def _delay(headers: dict) -> int:
        value = headers.get("retry-after", "5")
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,6}", value):
            raise LiveError("invalid Retry-After; remote operation may still be running")
        return max(1, int(value))

    def _pause(self, headers: dict) -> None:
        seconds = self._delay(headers)
        if seconds >= self._remaining():
            raise LiveError("timeout waiting for Retry-After; remote work may still be running; use get-results")
        time.sleep(seconds)

    @staticmethod
    def _resume_headers(state: dict) -> dict:
        seconds = max(0, math.ceil(state.get("poll_after", 0) - time.time()))
        return {"retry-after": str(seconds)}

    @staticmethod
    def _operation(response: Response) -> str:
        operation = response.headers.get("x-ms-operation-id")
        location = response.headers.get("location")
        if operation is None and isinstance(location, str):
            operation = _url(location).path.rsplit("/", 1)[-1]
        operation = _uuid(operation)
        if location is not None:
            _location(location, f"operations/{operation}")
        return operation

    def _wait_operation(self, operation: str, headers: dict, *,
                        expected: dict | None = None, state: dict | None = None) -> dict:
        for _ in range(60):
            if state is not None and expected is not None:
                state["poll_after"] = time.time() + self._delay(headers)
                self._write(self._state_path(expected), state)
            self._pause(headers)
            response = self._api(f"operations/{operation}")
            operation_status = self._ok(response).get("status")
            if operation_status == "Succeeded":
                return self._ok(self._api(f"operations/{operation}/result"))
            if operation_status not in ("NotStarted", "Running"):
                raise LiveError("Fabric operation failed or returned an unsupported status; inspect exact state IDs")
            headers = response.headers
        raise LiveError("operation polling timeout; remote work may still be running; use get-results")

    @staticmethod
    def _description(expected: dict) -> str:
        return f"GitHub Copilot Workshop; participant={expected['participant']}; sha256={expected['sha256']}"

    def _assert_item(self, item: dict, expected: dict, item_id: str | None = None) -> str:
        returned_id = _uuid(item.get("id"))
        if (item_id is not None and returned_id != item_id
                or item.get("workspaceId") != self.workspace or item.get("type") != "Notebook"
                or item.get("displayName") != expected["display_name"]
                or item.get("description") != self._description(expected)):
            raise LiveError("owned notebook metadata mismatch; no update or run performed")
        return returned_id

    def _created(self, item: dict, expected: dict, state: dict) -> dict:
        state["item_id"] = self._assert_item(item, expected)
        state["phase"] = "created"
        state.pop("poll_after", None)
        self._write(self._state_path(expected), state)
        return {"status": "Created", "item_id": state["item_id"], "display_name": expected["display_name"]}

    def _verify_owned(self, expected: dict, state: dict) -> None:
        item_id = _uuid(state.get("item_id"))
        item = self._ok(self._api(f"{self.base}/items/{item_id}"))
        self._assert_item(item, expected, item_id)
        response = self._api(f"{self.base}/notebooks/{item_id}/getDefinition?format=ipynb", method="post")
        definition = (self._wait_operation(self._operation(response), response.headers)
                      if response.status == 202 else self._ok(response))
        definition = _object(definition.get("definition"))
        parts = definition.get("parts")
        if definition.get("format", "ipynb") != "ipynb" or not isinstance(parts, list):
            raise LiveError("invalid owned notebook definition")
        contents = [part for part in parts if isinstance(part, dict) and part.get("path") == "notebook-content.ipynb"]
        if (len(contents) != 1 or any(not isinstance(part, dict) or part.get("path") not in
                                    ("notebook-content.ipynb", ".platform") for part in parts)):
            raise LiveError("untrusted notebook definition path")
        part = contents[0]
        try:
            payload = part.get("payload")
            if part.get("payloadType") != "InlineBase64" or not isinstance(payload, str) or len(payload) > MAX_BYTES:
                raise LiveError("invalid notebook definition payload")
            notebook = self._notebook(json.loads(base64.b64decode(payload, validate=True)))
        except (ValueError, TypeError, binascii.Error):
            raise LiveError("invalid notebook definition encoding") from None
        # Fabric may add presentation metadata; executable cells and lakehouse binding must not drift.
        metadata = notebook["metadata"]
        notebook["metadata"] = {
            key: metadata.get(key) for key in expected["content"]["metadata"]
        }
        if _digest(notebook) != expected["sha256"]:
            raise LiveError("remote notebook definition drift; refuse reuse or execution")

    def _publish(self, expected: dict, state: dict | None) -> dict:
        if state is not None:
            if state["phase"] != "created":
                raise LiveError("creation unresolved; use get-results or reconcile state; never resubmit blindly")
            self._verify_owned(expected, state)
            return {"status": "Reused", "item_id": state["item_id"], "display_name": expected["display_name"]}
        if any(item["displayName"].casefold() == expected["display_name"].casefold() for item in self._inventory()):
            raise LiveError("name already exists without owned state; never overwrite or adopt user items")
        state = {key: value for key, value in expected.items() if key != "content"} | {"phase": "submitting"}
        self._write(self._state_path(expected), state)
        payload = {"displayName": expected["display_name"], "description": self._description(expected),
                   "definition": {"format": "ipynb", "parts": [{
                       "path": "notebook-content.ipynb", "payloadType": "InlineBase64",
                       "payload": base64.b64encode(_encoded(expected["content"])).decode("ascii"),
                   }]}}
        response = self._api(f"{self.base}/notebooks", method="post", body=payload)
        if response.status == 202:
            state.update({"phase": "accepted", "operation_id": self._operation(response)})
            self._write(self._state_path(expected), state)
            item = self._wait_operation(state["operation_id"], response.headers, expected=expected, state=state)
        else:
            item = self._ok(response, 201)
        return self._created(item, expected, state)

    def _job(self, expected: dict, state: dict) -> tuple[dict, Response]:
        route = f"{self.base}/items/{state['item_id']}/jobs/instances/{state['job_id']}"
        response = self._api(route)
        body = self._ok(response)
        if body.get("id") != state["job_id"] or body.get("itemId") != state["item_id"]:
            raise LiveError("job response identity mismatch")
        status = body.get("status")
        if not isinstance(status, str) or status not in JOB_STATUSES:
            raise LiveError("unsupported job status; remote job may still be running")
        state["job_status"] = status
        if status in ("NotStarted", "InProgress"):
            state["poll_after"] = time.time() + self._delay(response.headers)
        else:
            state.pop("poll_after", None)
        self._write(self._state_path(expected), state)
        saved = {"id": state["job_id"], "itemId": state["item_id"], "status": status}
        if self.config.security.approved_data == "synthetic-only" and body.get("exitValue") is not None:
            value = body["exitValue"]
            if not isinstance(value, str) or len(value) > 65536:
                raise LiveError("unsupported notebook exit value")
            saved["exitValue"] = value
        relative = f"results/live/{self.workspace}/{state['job_id']}.json"
        self._write(self._path(relative), saved)
        return {"status": status, "item_id": state["item_id"], "job_id": state["job_id"],
                "results_file": relative}, response

    def _run(self, expected: dict, state: dict) -> dict:
        if state["phase"] != "created" or (
            state.get("job_id") and state.get("job_status") not in ("Completed", "Failed", "Cancelled", "Deduped")
        ):
            raise LiveError("previous creation/run unresolved; use get-results before submitting another run")
        self._verify_owned(expected, state)
        workspace_parameter, lakehouse_parameter = self._parameter_names(expected["content"])
        parameters = {
            workspace_parameter: {"type": "string", "value": self.workspace},
            lakehouse_parameter: {"type": "string", "value": self.config.fabric.lakehouse_id},
            "sandbox": {"type": "bool", "value": True},
            "approval": {"type": "string", "value": self.workspace},
            "batch_id": {"type": "string", "value": f"ghcp_{expected['participant']}_{expected['sha256'][:12]}"},
        }
        state["phase"] = "run-submitting"
        self._write(self._state_path(expected), state)
        response = self._api(f"{self.base}/items/{state['item_id']}/jobs/RunNotebook/instances",
                             method="post", body={"executionData": {"parameters": parameters}})
        if response.status != 202:
            raise LiveError("job was not accepted; inspect state before retrying")
        location = response.headers.get("location")
        if not isinstance(location, str):
            raise LiveError("missing job instance location; inspect state before retrying")
        job_id = _uuid(_url(location).path.rsplit("/", 1)[-1])
        _location(location, f"{self.base}/items/{state['item_id']}/jobs/instances/{job_id}")
        state.update({"job_id": job_id, "job_status": "NotStarted", "phase": "created"})
        self._write(self._state_path(expected), state)
        state["poll_after"] = time.time() + self._delay(response.headers)
        self._write(self._state_path(expected), state)
        for _ in range(120):
            self._pause(response.headers)
            result, response = self._job(expected, state)
            if result["status"] == "Completed":
                return result
            if result["status"] not in ("NotStarted", "InProgress"):
                raise LiveError("notebook job did not complete successfully; inspect saved results and Fabric run UI")
        raise LiveError("job polling timeout; remote job may still be running; use get-results")

    def execute(self, action: str, *, notebook: str | None = None, participant: str | None = None,
                approval: str | None = None) -> dict:
        self._guard(action, approval)
        expected = self._prepare(notebook, participant) if action not in ("preflight", "inventory") else None
        state = self._load_state(expected) if expected is not None else None
        if action in ("run-notebook", "get-results") and state is None:
            raise LiveError("owned notebook state is required; publish first")
        self.deadline = time.monotonic() + self.timeout
        self.requests = 0
        if expected is None:
            verified = self._preflight()
            return verified if action == "preflight" else {"items": self._inventory()}
        with self._lock(expected):
            state = self._load_state(expected)
            self._preflight()
            if action == "publish-notebook":
                return self._publish(expected, state)
            if state is None:
                raise LiveError("owned notebook state disappeared")
            if action == "run-notebook":
                return self._run(expected, state)
            if state["phase"] == "accepted":
                item = self._wait_operation(state["operation_id"], self._resume_headers(state),
                                            expected=expected, state=state)
                return self._created(item, expected, state)
            if state.get("job_id") and state["phase"] == "created":
                headers = self._resume_headers(state)
                if headers["retry-after"] != "0":
                    self._pause(headers)
                result, _ = self._job(expected, state)
                return result
            if state["phase"] == "created":
                item = self._ok(self._api(f"{self.base}/items/{state['item_id']}"))
                self._assert_item(item, expected, state["item_id"])
                return {"status": "NotRun", "item_id": state["item_id"], "display_name": expected["display_name"]}
            raise LiveError("request outcome unknown; reconcile exact state IDs/name manually; do not resubmit")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("demo.local.yaml"))
    parser.add_argument("--timeout", type=int, default=300, help="total seconds, 1-1800 (subprocesses capped at 30s)")
    actions = parser.add_subparsers(dest="action", required=True)
    for action in ACTIONS:
        command = actions.add_parser(action)
        if action not in ("preflight", "inventory"):
            command.add_argument("--notebook", choices=NOTEBOOKS, required=True)
            command.add_argument("--participant", required=True)
        if action in ("publish-notebook", "run-notebook"):
            command.add_argument("--approve-workspace", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    try:
        config = load_config(args.config)
    except (OSError, ValueError, TypeError):
        print("live adapter: configuration rejected; provide a strict complete local configuration", file=sys.stderr)
        return 1
    try:
        result = LiveAdapter(config, timeout=args.timeout).execute(
            args.action, notebook=getattr(args, "notebook", None), participant=getattr(args, "participant", None),
            approval=getattr(args, "approve_workspace", None),
        )
        print(json.dumps(result, sort_keys=True))
        return 1 if result.get("status") in ("Failed", "Cancelled", "Deduped") else 0
    except (LiveError, OSError) as exc:
        message = str(exc) if isinstance(exc, LiveError) else "local I/O failed; inspect state before retrying"
        print(f"live adapter: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
