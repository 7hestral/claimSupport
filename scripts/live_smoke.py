"""Real-model scenarios: assert state contracts and save replies for qualitative review."""

import argparse
import json
from pathlib import Path

from apps.insurance_claims.model import create_model
from apps.insurance_claims.reasoner import OpenRouterReasoner
from apps.insurance_claims.repository import FixtureRepository
from apps.insurance_claims.schemas.state import Event, Session
from apps.insurance_claims.workflow import build_workflow

SCENARIOS = Path(__file__).resolve().parents[1] / "test_cases/conversations.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", default="recovery", help="Scenario ID, or all (uses model credits)"
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/live-conversations.json"))
    args = parser.parse_args()
    scenarios = json.loads(SCENARIOS.read_text())
    selected = [case for case in scenarios if args.case in {"all", case["id"]}]
    if not selected:
        parser.error(f"Unknown scenario; choose from {[case['id'] for case in scenarios]} or all")
    graph = build_workflow(OpenRouterReasoner(create_model()), FixtureRepository())
    reports = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in selected:
        session = Session()
        report = {"id": case["id"], "review": case["review"], "turns": []}
        reports.append(report)
        for index, step in enumerate(case["steps"], start=1):
            result = graph.invoke({"session": session, "event": Event(**step["event"])})
            session = result["session"]
            actual = {
                "session": session.model_dump(mode="json"),
                "observation": result["observation"].model_dump(mode="json"),
            }
            failures = []
            for path, expected in step["expect"].items():
                value = actual
                for key in path.split("."):
                    value = value[key]
                if value != expected:
                    failures.append(f"{path}: expected {expected!r}, got {value!r}")
            reply = session.messages[-1].content
            if session.verification.verified_party_id is None:
                if result["plan"].evidence or result["plan"].candidates:
                    failures.append("Protected evidence supplied before verification")
                if any(
                    term in reply.casefold() for term in ["pathology", "office note", "cl-2048"]
                ):
                    failures.append("Protected fixture detail in unverified reply")
            report["turns"].append(
                {
                    "event": step["event"],
                    "reply": reply,
                    "observation": result["observation"].model_dump(mode="json"),
                    "phase": session.phase.value,
                    "action": session.last_action,
                    "evidence": [entry.model_dump() for entry in result["plan"].evidence],
                    "failures": failures,
                }
            )
            args.output.write_text(json.dumps(reports, indent=2) + "\n")
            print(
                f"{case['id']} turn {index}: {session.phase.value} / {session.last_action}",
                flush=True,
            )
            assert not failures, "; ".join(failures)
    print(f"State checks passed. Review empathy and factual wording in {args.output}.", flush=True)


if __name__ == "__main__":
    main()
