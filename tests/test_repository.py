import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

from tools.kit import build

ROOT = Path(__file__).resolve().parents[1]


def _markdown():
    ignored = {".git", ".venv", "node_modules", ".state", "results", ".pytest_cache"}
    return [
        path for path in ROOT.rglob("*.md")
        if not any(part in ignored for part in path.parts)
    ]


@pytest.mark.parametrize("path", _markdown(), ids=lambda path: str(path.relative_to(ROOT)))
def test_local_markdown_links_resolve(path):
    for raw in re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", path.read_text()):
        if re.match(r"^(https?:|mailto:|#)", raw):
            continue
        target = unquote(raw.split("#", 1)[0])
        assert (path.parent / target).exists(), f"{path.relative_to(ROOT)}: missing {raw}"


def test_committed_kit_matches_seeded_build(tmp_path):
    counts = build.build_kit(ROOT / "tools/source", tmp_path, None)
    assert counts == json.loads((ROOT / "tools/expected_counts.json").read_text())
    for path in (tmp_path / "data").rglob("*.csv"):
        assert path.read_bytes() == (ROOT / path.relative_to(tmp_path)).read_bytes(), path.name


def test_expected_results_document_is_generated():
    result = subprocess.run(
        [sys.executable, "-m", "tools.kit.expected_doc", "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_fixture_contacts_are_nonroutable_and_roles_explicit():
    for folder in ("tools/source/kcorp_plant", "data/landing/plant"):
        with (ROOT / folder / "FactAnomalyEvent.csv").open() as stream:
            assert all(row["NotificationRecipient"].endswith("@example.invalid") for row in csv.DictReader(stream))
        with (ROOT / folder / "DimPlant.csv").open() as stream:
            assert all(row["PlantManager"].startswith("Fictional manager ") for row in csv.DictReader(stream))


def test_optional_documents_match_reference_keys_and_are_pdf_files():
    with (ROOT / "data/landing/reference/utility_bills_ground_truth.csv").open() as stream:
        expected = {row["document_id"] for row in csv.DictReader(stream)}
    documents = list((ROOT / "data/landing/utility_bills").glob("*.pdf"))
    assert {path.stem for path in documents} == expected
    for path in documents:
        assert path.read_bytes().startswith(b"%PDF-"), path.name


def test_no_event_branding_or_source_tenant_ids_in_participant_text():
    for path in _markdown():
        text = path.read_text().lower()
        assert "astar" not in text, path
        assert not re.search(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", text), path


def test_ci_does_not_authorize_live_services():
    text = (ROOT / ".github/workflows/local-gates.yml").read_text()
    assert "contents: read" in text
    assert "id-token: write" not in text
    assert "secrets." not in text
    assert "fabric.preflight" not in text
