"""Stream structured model calls and emit diagnostics independently of business state."""

from collections.abc import Callable
from time import perf_counter
from typing import Literal
from uuid import uuid4

from langchain_core.utils.function_calling import convert_to_json_schema
from pydantic import Field

from .schemas.facts import OutputModel, StrictModel

TraceSink = Callable[[dict], None]


def discard_trace(event: dict) -> None:
    pass


class CallTrace(StrictModel):
    call_id: str = Field(default_factory=lambda: str(uuid4()))
    stage: Literal["extraction", "response"]
    model: str
    messages: list[dict[str, str]]
    response_format: dict
    output_text: str = ""
    parsed: dict | None = None
    usage: dict | None = None
    elapsed_ms: int = 0
    status: Literal["running", "succeeded", "failed"] = "running"
    error_type: str | None = None


def structured_call(
    model,
    schema: type[OutputModel],
    stage: str,
    messages: list[dict],
    emit: TraceSink,
    *,
    output_schema: dict | None = None,
) -> OutputModel:
    """Only validated, complete JSON can leave this model boundary."""
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "schema": output_schema
            if output_schema is not None
            else convert_to_json_schema(schema),
            "strict": True,
        },
    }
    trace = CallTrace(
        stage=stage, model=model.model_name, messages=messages, response_format=response_format
    )
    emit({"type": "start", "trace": trace.model_dump()})
    started = perf_counter()
    combined = None
    try:
        for chunk in model.bind(response_format=response_format).stream(messages):
            combined = chunk if combined is None else combined + chunk
            text = chunk.text
            trace.output_text += text
            if combined.usage_metadata is not None:
                trace.usage = dict(combined.usage_metadata)
            emit({"type": "delta", "call_id": trace.call_id, "text": text})
        parsed = schema.model_validate_json(trace.output_text)
        trace.parsed = parsed.model_dump(mode="json")
        trace.status = "succeeded"
        return parsed
    except (
        Exception
    ) as error:  # Model boundary: retain partial diagnostics, then propagate failure.
        trace.status = "failed"
        trace.error_type = type(error).__name__
        raise
    finally:
        trace.elapsed_ms = round((perf_counter() - started) * 1000)
        emit({"type": "finish", "trace": trace.model_dump()})
