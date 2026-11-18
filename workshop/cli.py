"""Named, offline-only workshop commands. Nothing here authenticates or calls Fabric."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from workshop.config import load_config
from workshop.curation import curate
from workshop.discovery import discover, validate_dictionary, validate_model
from workshop.io import ROOT, read_json, write_json
from workshop.reporting import apply_repair, compare_months, inject_fault, model_months, plan_repair, source_months

DATA = ROOT / "data/landing/plant"
GOLD = ROOT / "results/gold"
STATE = ROOT / ".state/model.json"
PLAN = ROOT / "results/repair-plan.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "config", "discover", "curate", "source-months", "report-fault", "report-check",
        "report-plan", "report-repair", "report-restore", "validate",
    ))
    parser.add_argument("--config", type=Path, default=ROOT / "demo.yaml")
    parser.add_argument("--approve-plan", default="")
    parser.add_argument("--dax-results", type=Path, help="normalized live DAX JSON under ignored results/")
    args = parser.parse_args(argv)
    try:
        load_config(args.config)
        if args.action == "config":
            result = {"status": "offline config valid", "live_acceptance": "not evaluated"}
        elif args.action == "discover":
            result = discover(DATA, ROOT / "fixtures/vendor-dictionary.json")
            write_json(ROOT / "results/discovery.json", result)
        elif args.action == "curate":
            result = curate(DATA, GOLD, ROOT / "data-model/dictionary.json")
            git_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True,
            ).stdout.strip()
            write_json(ROOT / ".state/generation-metadata.json", {
                "seed": 20261001, "dictionary_version": 1, "profile": "synthetic-core",
                "git_sha": git_sha, "timestamp": datetime.now(UTC).isoformat(),
                "dictionary_sha256": result["dictionary_sha256"], "row_counts": result["counts"],
            })
        elif args.action == "source-months":
            result = source_months(DATA)
            write_json(ROOT / "results/source-months.json", result)
        elif args.action == "report-fault":
            inject_fault(ROOT / "data-model/model.json", STATE)
            result = {"status": "offline fixture created; Date relationship inactive", "live_writes": False}
        elif args.action == "report-plan":
            result = plan_repair(STATE)
            write_json(PLAN, result)
        elif args.action == "report-repair":
            apply_repair(STATE, read_json(PLAN), args.approve_plan)
            result = {"status": "reviewed offline relationship repair applied"}
        elif args.action == "report-restore":
            current_hash = hashlib.sha256(STATE.read_bytes()).hexdigest()
            if not args.approve_plan or args.approve_plan != current_hash:
                raise ValueError("restore requires current offline model SHA256 in --approve-plan")
            current = read_json(STATE)
            original = read_json(STATE.with_suffix(".original.json"))
            if current.get("scope") != "offline-synthetic" or original.get("scope") != "offline-synthetic":
                raise ValueError("restore is limited to the offline-synthetic fixture")
            write_json(STATE, original)
            result = {"status": "original healthy offline model restored"}
        elif args.action == "report-check":
            expected = source_months(DATA)
            if args.dax_results is None:
                actual = model_months(GOLD, STATE)
                mode = "offline Date-filter simulator, not live DAX execution"
            else:
                path = args.dax_results.resolve()
                if not path.is_relative_to((ROOT / "results").resolve()):
                    raise ValueError("DAX evidence must be stored under ignored results/")
                actual = read_json(path)
                mode = "provided DAX evidence; provenance must be independently reviewed"
            problems = compare_months(expected, actual)
            result = {"mode": mode, "months": len(expected), "problems": problems, "passed": not problems}
            write_json(ROOT / "results/monthly-check.json", result)
            evidence = ROOT / "results" / ("monthly-before.json" if problems else "monthly-after.json")
            if not evidence.exists():
                write_json(evidence, result)
            if problems:
                print(json.dumps(result, indent=2))
                return 1
        else:
            graph = validate_dictionary(ROOT / "data-model/dictionary.json", DATA)
            model = read_json(ROOT / "data-model/model.json")
            validate_model(graph, model)
            result = {"status": "dictionary and core model coherent", "relationships": len(model["relationships"])}
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
