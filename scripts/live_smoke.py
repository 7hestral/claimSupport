"""Run real-model state checks and save reviewable transcripts for the SOP review skill."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from apps.insurance_claims.model import create_model
from apps.insurance_claims.monitoring import flush_monitoring
from apps.insurance_claims.reasoner import OpenRouterReasoner
from apps.insurance_claims.repository import FixtureRepository
from apps.insurance_claims.workflow import build_workflow
from scripts.eval_cases import load_cases, run_case, write_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", nargs="+", default=["recovery"], help="Scenario IDs, or all")
    parser.add_argument("--list", action="store_true", help="List cases without model calls")
    parser.add_argument("--output", type=Path, default=Path("outputs/live-conversations.json"))
    args = parser.parse_args()
    cases = load_cases()
    if args.list:
        for case in cases:
            print(f"{case.id}: {len(case.steps)} events — {case.review}")
        return
    unknown = set(args.case) - {"all", *(case.id for case in cases)}
    if unknown:
        parser.error(f"Unknown scenarios: {sorted(unknown)}; use --list")
    selected = [case for case in cases if "all" in args.case or case.id in args.case]
    model = create_model()
    graph = build_workflow(OpenRouterReasoner(model), FixtureRepository())
    report = {
        "format_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "model": model.model_name,
        "selected_cases": [case.id for case in selected],
        "execution_status": "running",
        "semantic_review": "pending",
        "cases": [],
    }
    failures = 0
    for case in selected:
        case_report = {
            "id": case.id,
            "review": case.review,
            "setup": case.setup.model_dump(mode="json", exclude_none=True),
            "expected_events": len(case.steps),
            "turns": [],
        }
        report["cases"].append(case_report)
        for turn in run_case(graph, case):
            case_report["turns"].append(turn)
            failures += len(turn["failures"])
            write_report(args.output, report)
            status = "; ".join(turn["failures"]) or "state checks passed"
            print(f"{case.id} turn {turn['turn']}: {status}", flush=True)
    report["execution_status"] = "completed_with_failures" if failures else "completed"
    flush_monitoring()
    report["finished_at"] = datetime.now(UTC).isoformat()
    write_report(args.output, report)
    print(
        f"{failures} deterministic failures. Text review still required: {args.output}", flush=True
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
