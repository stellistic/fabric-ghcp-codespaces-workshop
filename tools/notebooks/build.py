"""Deterministically build standalone, guarded Fabric notebooks and the core contract."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
SOURCE_REVISION = "d0d8c57a5dfc3d9eff8a2339c0266395367733df"
TARGETS = {
    "02_bronze_ingest.py": "notebooks/02_bronze_ingest.ipynb",
    "03_silver_transform.py": "notebooks/03_silver_transform.ipynb",
    "04_silver_dims_catchup.py": "notebooks/04_silver_dims_catchup.ipynb",
    "05_gold_star_schema.py": "notebooks/05_gold_star_schema.ipynb",
    "07_semantic_model_catchup.py": "notebooks/07_semantic_model_catchup.ipynb",
}
METADATA = {
    "language_info": {"name": "python"},
    "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
    "microsoft": {"language": "python", "language_group": "synapse_pyspark"},
    "kernel_info": {"name": "synapse_pyspark"},
}
PARAMETERS = '''workspace_id = ""
lakehouse_id = ""
sandbox = False
approval = ""
batch_id = ""
'''
MODEL_PARAMETERS = '''expected_model_id = ""
model_workspace_id = ""
apply_changes = False
apply_approval = ""
reviewed_diff_hash = ""
selected_changes = []
verify_model = False
'''
GUARD_CALL = '''
def require_sandbox():
    assert_sandbox_context(
        notebookutils.runtime.context, workspace_id=workspace_id, lakehouse_id=lakehouse_id,
        sandbox=sandbox, approval=approval, batch_id=batch_id,
    )

require_sandbox()
'''


def cell(kind: str, source: str, *, parameters: bool = False) -> dict:
    result = {"cell_type": kind, "metadata": {}, "source": source.rstrip() + "\n"}
    if parameters:
        result["metadata"]["tags"] = ["parameters"]
    if kind == "code":
        ast.parse(source)
        result.update(execution_count=None, outputs=[])
    return result


def parse_cells(text: str) -> list[dict]:
    cells = []
    kind = None
    lines = []

    def flush():
        if kind is not None and any(line.strip() for line in lines):
            content = lines
            if kind == "markdown":
                content = [line[2:] if line.startswith("# ") else line.lstrip("#") for line in lines]
            cells.append(cell(kind, "\n".join(content).strip()))

    for line in text.splitlines():
        if line.startswith("# %%"):
            flush()
            kind = "markdown" if "[markdown]" in line else "code"
            lines = []
        else:
            lines.append(line)
    flush()
    if not cells or not any(c["cell_type"] == "code" for c in cells):
        raise ValueError("Notebook source must contain percent-format Python code cells")
    return cells


def core_contract() -> dict:
    tree = ast.parse((SRC / "07_semantic_model_catchup.py").read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"TABLES", "RELATIONSHIPS", "MEASURES"}:
                    values[target.id] = ast.literal_eval(node.value)
    result = {
        "version": 1,
        "tables": values["TABLES"],
        "relationships": [
            dict(zip(("from_table", "from_column", "to_table", "to_column"), relation, strict=True), active=True)
            for relation in values["RELATIONSHIPS"]
        ],
        "measures": [
            dict(zip(("table", "name", "dax", "format"), measure, strict=True))
            for measure in values["MEASURES"]
        ],
    }
    if tuple(len(result[k]) for k in ("tables", "relationships", "measures")) != (12, 18, 14):
        raise ValueError("Core contract must contain exactly 12 tables, 18 relationships, and 14 measures")
    if "utility" in json.dumps(result).lower():
        raise ValueError("An optional appendix cannot enter the core contract")
    return result


def render(src: Path) -> str:
    original = parse_cells(src.read_text(encoding="utf-8"))
    model = src.name.startswith("07_")
    cells = [
        cell("markdown", "# GitHub Copilot Workshop · Microsoft Fabric\n\n"
             "GitHub Copilot is the coding assistant; Fabric is the execution target. "
             "Synthetic manufacturing data only. See `docs/notebooks.md` before running. "
             "Use a disposable sandbox: data notebooks perform guarded full refreshes, not production ingestion."),
        cell("code", PARAMETERS + (MODEL_PARAMETERS if model else ""), parameters=True),
        cell("code", (HERE / "guard.py").read_text(encoding="utf-8") + GUARD_CALL),
    ]
    if model:
        cells.append(cell("code", (HERE / "recovery.py").read_text(encoding="utf-8")))
        queries = {
            "CHECK_MEASURES_DAX": (ROOT / "queries/check-measures.dax").read_text(encoding="utf-8"),
            "MONTHLY_DAX": (ROOT / "queries/monthly.dax").read_text(encoding="utf-8"),
        }
        cells.append(cell("code", "\n".join(f"{key} = {value!r}" for key, value in queries.items())))
    else:
        cells.append(cell("code", (HERE / "lineage.py").read_text(encoding="utf-8")
                          + "\nconfigure_lineage(spark, require_sandbox, batch_id, "
                          + f"{src.stem!r}, {SOURCE_REVISION!r})\n"))
    for original_cell in original:
        if original_cell["cell_type"] == "code":
            original_cell["source"] = "require_sandbox()\n" + original_cell["source"]
        cells.append(original_cell)
    if not model:
        cells.append(cell("code", "require_sandbox()\nemit_run_metadata()\n"))
    for index, content in enumerate(cells):
        content["id"] = hashlib.sha256(f"{src.name}:{index}".encode()).hexdigest()[:16]
    return json.dumps({"cells": cells, "metadata": METADATA, "nbformat": 4, "nbformat_minor": 5},
                      indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    outputs = {}
    try:
        # Validate all inputs before writing any output; missing sources must never be skipped.
        for source, target in TARGETS.items():
            outputs[target] = render(SRC / source)
        outputs["data-model/model.json"] = json.dumps(core_contract(), indent=2, ensure_ascii=False) + "\n"
    except (OSError, ValueError, KeyError, SyntaxError) as error:
        print(f"Notebook build failed: {error}", file=sys.stderr)
        return 1
    stale = []
    for target, rendered in outputs.items():
        path = ROOT / target
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != rendered:
                stale.append(target)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
            print(f"wrote {target}")
    if stale:
        print("stale outputs (run python -m tools.notebooks.build):\n  " + "\n  ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
