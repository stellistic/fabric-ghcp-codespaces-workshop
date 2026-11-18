"""Offline notebook contracts: never import Spark, authenticate, or contact Fabric."""

import ast
import importlib.util
import json
import re
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import nbformat
import pytest

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "tools" / "notebooks"
WORKSPACE = "11111111-1111-4111-8111-111111111111"
LAKEHOUSE = "22222222-2222-4222-8222-222222222222"
MODEL = "33333333-3333-4333-8333-333333333333"


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, NB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parameters():
    return dict(workspace_id=WORKSPACE, lakehouse_id=LAKEHOUSE, sandbox=True,
                approval=WORKSPACE, batch_id="offline-test")


def context():
    return {"currentWorkspaceId": WORKSPACE, "defaultLakehouseId": LAKEHOUSE}


def test_core_contract_is_utility_independent():
    contract = json.loads((ROOT / "data-model/model.json").read_text())
    assert set(contract) == {"version", "tables", "relationships", "measures"}
    assert contract["version"] == 1
    assert len(contract["tables"]) == 12
    assert len(contract["relationships"]) == 18
    assert len(contract["measures"]) == 14
    assert "utility" not in json.dumps(contract).lower()
    assert "agg_plant_month" not in contract["tables"]
    for relationship in contract["relationships"]:
        assert set(relationship) == {"from_table", "from_column", "to_table", "to_column", "active"}
        assert relationship["active"] is True
        assert relationship["from_table"] in contract["tables"]
        assert relationship["to_table"] in contract["tables"]
    for measure in contract["measures"]:
        assert set(measure) == {"table", "name", "dax", "format"}
        assert measure["table"] in contract["tables"]
    measures = {m["name"]: m["dax"] for m in contract["measures"]}
    assert measures["Scrap Rate %"] == "DIVIDE ( [Scrap Units], [Actual Units] + [Scrap Units] )"
    assert measures["Production Attainment %"] == "DIVIDE ( [Actual Units], [Planned Units] )"
    for query in ("check-measures.dax", "monthly.dax"):
        text = (ROOT / "queries" / query).read_text()
        assert "utility" not in text.lower()
        assert "[Actual Units]" in text
    assert "[Scrap Rate %]" in (ROOT / "queries/check-measures.dax").read_text()
    monthly = (ROOT / "queries/monthly.dax").read_text()
    assert "'dim_date'[YearMonth]" in monthly
    assert "'dim_plant'" not in monthly
    assert re.findall(r'"([^"]+)",\s*\[([^\]]+)\]', monthly) == [("Actual Units", "Actual Units")]


def test_sandbox_guard_accepts_only_matching_explicit_ids():
    guard = load_module("guard")
    guard.assert_sandbox_context(context(), **parameters())


@pytest.mark.parametrize("change", [
    {"workspace_id": ""}, {"lakehouse_id": ""}, {"workspace_id": "workshop"},
    {"lakehouse_id": "lakehouse"}, {"sandbox": False}, {"sandbox": "true"},
    {"approval": ""}, {"approval": LAKEHOUSE}, {"batch_id": ""},
    {"batch_id": "../other"}, {"workspace_id": WORKSPACE.upper() + " "},
])
def test_guard_rejects_bad_parameters(change):
    values = parameters() | change
    with pytest.raises(ValueError):
        load_module("guard").assert_sandbox_context(context(), **values)


@pytest.mark.parametrize("runtime", [
    {}, {"currentWorkspaceName": "workshop", "defaultLakehouseName": "plant"},
    {"currentWorkspaceId": LAKEHOUSE, "defaultLakehouseId": LAKEHOUSE},
    {"currentWorkspaceId": WORKSPACE, "defaultLakehouseId": MODEL},
    {"currentWorkspaceId": WORKSPACE}, None,
])
def test_guard_fails_closed_for_wrong_or_missing_runtime(runtime):
    with pytest.raises(ValueError):
        load_module("guard").assert_sandbox_context(runtime, **parameters())


def test_generated_notebooks_are_fresh_valid_and_guarded(monkeypatch):
    build = load_module("build")
    assert len(build.TARGETS) == 5
    assert subprocess.run([sys.executable, "-m", "tools.notebooks.build", "--check"],
                          cwd=ROOT, capture_output=True, text=True).returncode == 0
    for source, target in build.TARGETS.items():
        path = ROOT / target
        notebook = json.loads(path.read_text())
        nbformat.validate(nbformat.from_dict(notebook))
        assert path.read_text() == build.render(NB / "src" / source)
        code = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        assert "parameters" in code[0]["metadata"]["tags"]
        defaults = {}
        exec("".join(code[0]["source"]), defaults)
        assert defaults["workspace_id"] == defaults["lakehouse_id"] == ""
        assert defaults["sandbox"] is False
        assert defaults["approval"] == defaults["batch_id"] == ""
        for cell in code:
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
            ast.parse("".join(cell["source"]))
        # Executing every notebook with defaults must fail before any Spark/model operation.
        spark = Mock()
        namespace = {"spark": spark, "notebookutils": types.SimpleNamespace(
            runtime=types.SimpleNamespace(context=context()))}
        with pytest.raises(ValueError):
            for cell in code:
                exec("".join(cell["source"]), namespace)
        assert spark.mock_calls == []
        # Authorized mocked startup must also execute the injected guard.
        namespace.update(parameters())
        exec("".join(code[1]["source"]), namespace)
        assert callable(namespace["assert_sandbox_context"])
    core = (ROOT / "notebooks/07_semantic_model_catchup.ipynb").read_text()
    assert "utility" not in core.lower()
    assert "readonly=True" in core
    assert "apply_changes = False" in core
    assert "reviewed_diff_hash" in core


def test_build_fails_for_missing_sources_and_detects_stale_output(monkeypatch):
    build = load_module("build")
    monkeypatch.setattr(build, "TARGETS", {"missing.py": "notebooks/missing.ipynb"})
    assert build.main(["--check"]) == 1
    assert build.main([]) == 1
    monkeypatch.setattr(build, "TARGETS", {"02_bronze_ingest.py": "notebooks/missing.ipynb"})
    assert build.main(["--check"]) == 1


def test_gold_contract_counts_and_lineage_preserve_source_math():
    build = load_module("build")
    gold = (NB / "src/05_gold_star_schema.py").read_text()
    tree = ast.parse(gold)
    counts = next(ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "EXPECTED_GOLD" for t in node.targets))
    assert len(counts) == 13
    assert counts["agg_plant_month"] == 120
    assert counts["fact_production_run"] == 3629
    assert counts["fact_quality_inspection"] == 2729
    assert counts["fact_customer_order"] == 4560
    assert all(str(value) in gold for value in (1032704, 33404, 1095550, 0.0313, 0.9426))
    bronze = build.render(NB / "src/02_bronze_ingest.py")
    silver = build.render(NB / "src/03_silver_transform.py")
    assert all(column in bronze for column in
               ("_ingest_timestamp", "_source_file", "_source_system", "_batch_id"))
    assert all(column in silver for column in ("_processed_timestamp", "_record_hash"))
    assert "add_silver_lineage" in (NB / "src/04_silver_dims_catchup.py").read_text()


def fake_tom():
    contract = json.loads((ROOT / "data-model/model.json").read_text())
    tables = []
    for name in contract["tables"]:
        columns = {r[column] for r in contract["relationships"]
                   for table, column in (("from_table", "from_column"), ("to_table", "to_column"))
                   if r[table] == name}
        tables.append(types.SimpleNamespace(Name=name, Columns=[
            types.SimpleNamespace(Name=column) for column in sorted(columns)], Measures=[]))
    wrapper = types.SimpleNamespace(model=types.SimpleNamespace(Tables=tables, Relationships=[]))
    wrapper.add_measure = Mock()
    wrapper.add_relationship = Mock()
    return wrapper


def test_recovery_plan_readonly_scoped_and_apply_requires_review():
    recovery = load_module("recovery")
    contract = json.loads((ROOT / "data-model/model.json").read_text())
    tom = fake_tom()
    plan = recovery.make_plan(tom, contract, WORKSPACE, MODEL)
    assert len(plan["changes"]) == 32
    assert len(plan["digest"]) == 64
    assert plan["snapshot"]["workspace_id"] == WORKSPACE
    assert plan["snapshot"]["model_id"] == MODEL
    assert tom.add_measure.call_count == tom.add_relationship.call_count == 0
    with pytest.raises(ValueError):
        recovery.apply_plan(tom, contract, plan, reviewed_diff_hash="", selected_changes=[], tom_types=None)
    assert tom.add_measure.call_count == tom.add_relationship.call_count == 0
    chosen = next(c["key"] for c in plan["changes"] if c["kind"] == "measure")
    recovery.apply_plan(tom, contract, plan, reviewed_diff_hash=plan["digest"],
                        selected_changes=[chosen], tom_types=None)
    assert tom.add_measure.call_count == 1
    assert tom.add_relationship.call_count == 0


def test_recovery_detects_drift_and_rejects_unknown_scope():
    recovery = load_module("recovery")
    contract = json.loads((ROOT / "data-model/model.json").read_text())
    tom = fake_tom()
    plan = recovery.make_plan(tom, contract, WORKSPACE, MODEL)
    for scope in ([], ["measure:not-a-core-measure"]):
        with pytest.raises(ValueError):
            recovery.apply_plan(tom, contract, plan, reviewed_diff_hash=plan["digest"],
                                selected_changes=scope, tom_types=None)
    tom.model.Tables[0].Columns.append(types.SimpleNamespace(Name="UnreviewedColumn"))
    with pytest.raises(ValueError, match="drift"):
        recovery.apply_plan(tom, contract, plan, reviewed_diff_hash=plan["digest"],
                            selected_changes=[plan["changes"][0]["key"]], tom_types=None)
    assert tom.add_measure.call_count == tom.add_relationship.call_count == 0


def test_recovery_preserves_unrelated_and_original_definitions():
    recovery = load_module("recovery")
    contract = json.loads((ROOT / "data-model/model.json").read_text())
    tom = fake_tom()
    table = next(t for t in tom.model.Tables if t.Name == "fact_production_run")
    original = types.SimpleNamespace(Name="Actual Units", Expression="SUM ( [OldColumn] )",
                                     FormatString="0.0", Table=table)
    unrelated = types.SimpleNamespace(Name="User Measure", Expression="42", FormatString="0", Table=table)
    table.Measures.extend([original, unrelated])
    plan = recovery.make_plan(tom, contract, WORKSPACE, MODEL)
    change = next(c for c in plan["changes"] if c["key"] == "measure:fact_production_run:Actual Units")
    assert change["before"]["dax"] == "SUM ( [OldColumn] )"
    recovery.apply_plan(tom, contract, plan, reviewed_diff_hash=plan["digest"],
                        selected_changes=[change["key"]], tom_types=None)
    assert original.Expression == "SUM ( 'fact_production_run'[ActualUnits] )"
    assert unrelated.Expression == "42"
    assert change["before"]["dax"] == "SUM ( [OldColumn] )"


def test_recovery_rejects_reverse_relationships_without_deleting_them():
    recovery = load_module("recovery")
    tom = fake_tom()
    table_by_name = {t.Name: t for t in tom.model.Tables}
    rel = types.SimpleNamespace(Name="user-reversed",
        FromTable=table_by_name["dim_date"], FromColumn=types.SimpleNamespace(Name="DateKey"),
        ToTable=table_by_name["fact_production_run"], ToColumn=types.SimpleNamespace(Name="DateKey"),
        IsActive=True, FromCardinality="One", ToCardinality="Many",
        CrossFilteringBehavior="OneDirection")
    tom.model.Relationships.append(rel)
    contract = json.loads((ROOT / "data-model/model.json").read_text())
    with pytest.raises(ValueError, match="revers"):
        recovery.make_plan(tom, contract, WORKSPACE, MODEL)
    assert tom.model.Relationships == [rel]


class NamedCollection(list):
    def __getitem__(self, key):
        if isinstance(key, str):
            return next(value for value in self if value.Name == key)
        return super().__getitem__(key)

    def Add(self, value):
        self.append(value)


def mocked_model_runtime(monkeypatch):
    """Run the actual generated model cells with entirely in-memory SDK stand-ins."""
    model = fake_tom().model
    model.Tables = NamedCollection(model.Tables)
    model.Relationships = NamedCollection(model.Relationships)
    for table in model.Tables:
        table.Measures = NamedCollection(table.Measures)
        table.Columns = NamedCollection(table.Columns)
    model.Database = types.SimpleNamespace(ID=MODEL)
    model.SaveChanges = Mock()
    server = Mock()
    server.Databases = {MODEL: types.SimpleNamespace(Model=model)}
    fabric = types.ModuleType("sempy.fabric")
    fabric.create_tom_server = Mock(return_value=server)
    fabric.refresh_tom_cache = Mock()
    fabric.evaluate_dax = Mock()
    sempy = types.ModuleType("sempy")
    sempy.fabric = fabric
    microsoft = types.ModuleType("Microsoft")
    analysis = types.ModuleType("Microsoft.AnalysisServices")
    tom_types = types.ModuleType("Microsoft.AnalysisServices.Tabular")
    tom_types.JsonSerializer = types.SimpleNamespace(SerializeDatabase=Mock(
        return_value=json.dumps({"id": MODEL, "originalDefinition": "preserve-for-rollback"})))
    tom_types.Measure = types.SimpleNamespace
    analysis.Tabular = tom_types
    microsoft.AnalysisServices = analysis
    for name, module in (
        ("sempy", sempy), ("sempy.fabric", fabric), ("Microsoft", microsoft),
        ("Microsoft.AnalysisServices", analysis), ("Microsoft.AnalysisServices.Tabular", tom_types),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    fs = Mock()
    fs.exists.return_value = False
    fs.put.return_value = True
    fs.runtime_context = context()
    notebookutils = types.SimpleNamespace(runtime=types.SimpleNamespace(context=fs.runtime_context), fs=fs)

    def run(**overrides):
        notebook = json.loads((ROOT / "notebooks/07_semantic_model_catchup.ipynb").read_text())
        namespace = {"notebookutils": notebookutils, "spark": Mock(), "display": Mock()}
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                exec("".join(cell["source"]), namespace)
                if "parameters" in cell["metadata"].get("tags", []):
                    namespace.update(parameters(), expected_model_id=MODEL, model_workspace_id=WORKSPACE)
                    namespace.update(overrides)
        return namespace

    return run, fabric, model, fs


def test_model_notebook_default_is_model_readonly_and_preserves_full_snapshot(monkeypatch):
    run, fabric, model, fs = mocked_model_runtime(monkeypatch)
    namespace = run()
    fabric.create_tom_server.assert_called_once_with(dataset=MODEL, workspace=WORKSPACE, readonly=True)
    assert model.SaveChanges.call_count == 0
    assert fabric.evaluate_dax.call_count == 0
    saved = json.loads(fs.put.call_args.args[1])
    assert saved["snapshot"]["original_database_definition"]["originalDefinition"] == "preserve-for-rollback"
    assert saved["digest"] == namespace["plan"]["digest"]
    assert fs.put.call_args.args[2] is False
    assert namespace["spark"].mock_calls == []


@pytest.mark.parametrize("overrides", [
    {"expected_model_id": ""}, {"expected_model_id": "model-name"},
    {"model_workspace_id": LAKEHOUSE}, {"apply_changes": "true"}, {"verify_model": "true"},
])
def test_model_notebook_rejects_bad_target_before_sdk_or_snapshot_write(monkeypatch, overrides):
    run, fabric, model, fs = mocked_model_runtime(monkeypatch)
    with pytest.raises(ValueError):
        run(**overrides)
    assert fabric.create_tom_server.call_count == 0
    assert model.SaveChanges.call_count == fs.put.call_count == 0


def test_model_notebook_requires_separate_approval_then_saves_only_chosen_measure(monkeypatch):
    run, fabric, model, fs = mocked_model_runtime(monkeypatch)
    plan = run()["plan"]
    with pytest.raises(ValueError):
        run(apply_changes=True, reviewed_diff_hash=plan["digest"],
            selected_changes=["measure:fact_production_run:Actual Units"])
    assert model.SaveChanges.call_count == 0
    fabric.create_tom_server.reset_mock()
    run(apply_changes=True, apply_approval=MODEL, reviewed_diff_hash=plan["digest"],
        selected_changes=["measure:fact_production_run:Actual Units"])
    assert [call.kwargs for call in fabric.create_tom_server.call_args_list] == [
        {"dataset": MODEL, "workspace": WORKSPACE, "readonly": True},
        {"dataset": MODEL, "workspace": WORKSPACE, "readonly": False},
    ]
    assert model.SaveChanges.call_count == 1
    assert [(table.Name, measure.Name) for table in model.Tables for measure in table.Measures] == [
        ("fact_production_run", "Actual Units"),
    ]
    assert len(model.Relationships) == 0


def test_model_notebook_snapshot_failure_prevents_writable_connection(monkeypatch):
    run, fabric, model, fs = mocked_model_runtime(monkeypatch)
    fs.put.return_value = False
    with pytest.raises(ValueError, match="preserve"):
        run(apply_changes=True, apply_approval=MODEL)
    fabric.create_tom_server.assert_called_once_with(dataset=MODEL, workspace=WORKSPACE, readonly=True)
    assert model.SaveChanges.call_count == 0


def test_model_notebook_rechecks_approval_immediately_before_snapshot_put(monkeypatch):
    run, fabric, model, fs = mocked_model_runtime(monkeypatch)
    runtime = fs.runtime_context

    def detach_lakehouse(_path):
        runtime["defaultLakehouseId"] = MODEL
        return False

    fs.exists.side_effect = detach_lakehouse
    with pytest.raises(ValueError):
        run()
    assert fs.put.call_count == 0
    assert model.SaveChanges.call_count == 0


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_model_verification_rejects_nonfinite_headline_values(monkeypatch, invalid):
    run, fabric, model, fs = mocked_model_runtime(monkeypatch)
    result = types.SimpleNamespace(iloc=[types.SimpleNamespace(
        tolist=lambda: [1095550, invalid, 33404, 0.0313, 0.9426])])
    fabric.evaluate_dax.side_effect = [
        result, AssertionError("Non-finite headline value escaped validation"),
    ]
    with pytest.raises(ValueError, match="Actual Units"):
        run(verify_model=True)
    assert fabric.evaluate_dax.call_count == 1
    assert model.SaveChanges.call_count == 0
