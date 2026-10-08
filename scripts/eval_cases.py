"""Scenario contracts and deterministic checks; prose is reviewed separately by Codex."""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue, TypeAdapter

from apps.insurance_claims.monitoring import observe_turn
from apps.insurance_claims.schemas.facts import StrictModel
from apps.insurance_claims.schemas.state import Event, Session

SCENARIOS = Path(__file__).resolve().parents[1] / "test_cases"


class Setup(StrictModel):
    now: datetime | None = None
    consent_scenario: Literal["default", "timeout"] = "default"


class Step(StrictModel):
    event: Event
    expect: dict[str, JsonValue] = Field(default_factory=dict)
    present: list[str] = Field(default_factory=list)
    includes: dict[str, list[JsonValue]] = Field(default_factory=dict)


class Case(StrictModel):
    id: str
    review: str
    setup: Setup = Field(default_factory=Setup)
    steps: list[Step] = Field(min_length=1)


def load_cases(directory: Path = SCENARIOS) -> list[Case]:
    cases = [
        case
        for path in sorted(directory.glob("*.json"))
        for case in TypeAdapter(list[Case]).validate_json(path.read_text())
    ]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Scenario IDs must be unique across files.")
    return cases


def lookup(actual: dict, path: str):
    value = actual
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise KeyError(path)
        value = value[key]
    return value


def check_step(step: Step, actual: dict) -> list[str]:
    failures = []
    for path in dict.fromkeys([*step.expect, *step.present, *step.includes]):
        try:
            value = lookup(actual, path)
        except KeyError:
            failures.append(f"{path}: missing field")
            continue
        if path in step.expect and value != step.expect[path]:
            failures.append(f"{path}: expected {step.expect[path]!r}, got {value!r}")
        if path in step.present and (value is None or value == "" or value == [] or value == {}):
            failures.append(f"{path}: expected a populated field")
        if path in step.includes and (
            not isinstance(value, list) or any(item not in value for item in step.includes[path])
        ):
            failures.append(f"{path}: expected list to include {step.includes[path]!r}")
    return failures


def run_case(graph, case: Case) -> Iterator[dict]:
    session = Session(**case.setup.model_dump(exclude_none=True))
    for index, step in enumerate(case.steps, start=1):
        before = session.model_dump(mode="json", exclude={"messages"})
        try:
            with observe_turn(session, step.event, source="evaluation", case_id=case.id) as trace:
                result = graph.invoke({"session": session, "event": step.event})
                trace.finish(result["session"])
        except Exception as error:  # noqa: BLE001 -- Report batch errors without losing other cases.
            # Evaluation boundary: preserve the failed case and let other scenarios run.
            yield {
                "turn": index,
                "event": step.event.model_dump(mode="json"),
                "before": before,
                "error": {"type": type(error).__name__, "message": str(error)},
                "failures": [
                    "Workflow did not produce a validated reply; remaining turns skipped."
                ],
            }
            return
        session = result["session"]
        actual = {
            "session": session.model_dump(mode="json", exclude={"messages"}),
            "observation": result["observation"].model_dump(mode="json"),
            "plan": result["plan"].model_dump(mode="json"),
            "draft": result["draft"].model_dump(mode="json"),
        }
        failures = check_step(step, actual)
        if session.verification.verified_party_id is None and (
            result["plan"].evidence or result["plan"].candidates
        ):
            failures.append("Protected evidence supplied before verification")
        yield {
            "turn": index,
            "event": step.event.model_dump(mode="json"),
            "before": before,
            "monitoring": trace.reference(),
            **actual,
            "failures": failures,
        }


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
