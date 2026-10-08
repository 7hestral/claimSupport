"""Local tester console; model diagnostics never become customer-visible claim evidence."""

import json

import streamlit as st

from .llm_calls import CallTrace


def record_event(traces: dict[str, CallTrace], event: dict) -> CallTrace:
    if event["type"] == "delta":
        trace = traces[event["call_id"]]
        trace.output_text += event["text"]
    else:
        trace = CallTrace.model_validate(event["trace"])
        traces[trace.call_id] = trace
    return trace


def usage_rows(traces: list[CallTrace]) -> list[dict]:
    rows = []
    for stage in ("extraction", "response"):
        calls = [trace for trace in traces if trace.stage == stage]
        reported = [trace.usage for trace in calls if trace.usage is not None]
        rows.append(
            {
                "LLM": stage,
                "Calls": len(calls),
                "Input tokens": sum(u["input_tokens"] for u in reported) if reported else None,
                "Output tokens": sum(u["output_tokens"] for u in reported) if reported else None,
                "Total tokens": sum(u["total_tokens"] for u in reported) if reported else None,
                "Usage unavailable": len(calls) - len(reported),
            }
        )
    return rows


def debug_console(traces: dict[str, CallTrace]) -> None:
    st.subheader("LLM debug console")
    st.caption(
        "Local tester view: raw inputs include supplied identity details. No API key or request headers are recorded."
    )
    if not traces:
        st.info("Model calls will appear here when you send a message.")
        return
    calls = list(traces.values())
    st.table(usage_rows(calls))
    st.caption(
        "Provider-reported tokens across this conversation, including failed attempts when usage was returned. Missing usage is not estimated. Fixed replies make no response-model call."
    )
    st.caption(
        "Call success means valid model output; the SOP may still reject a turn before saving it."
    )
    for number, trace in reversed(list(enumerate(calls, start=1))):
        with st.expander(
            f"{number}. {trace.stage} · {trace.status} · {trace.elapsed_ms / 1000:.2f}s"
        ):
            st.caption(f"Model: {trace.model} · Call: {trace.call_id}")
            st.markdown("**Input messages**")
            st.json(trace.messages, expanded=False)
            st.markdown("**Requested output schema**")
            st.json(trace.response_format, expanded=False)
            st.markdown("**Raw output stream**")
            st.code(trace.output_text, language="json")
            st.markdown("**Validated output**")
            st.json(trace.parsed)
            st.markdown("**Token usage**")
            st.json(trace.usage)
            if trace.error_type:
                st.error(
                    f"Call failed: {trace.error_type}. Partial output was not applied to the conversation."
                )
    st.download_button(
        "Download model traces",
        json.dumps([call.model_dump() for call in calls], indent=2),
        file_name="model-traces.json",
        mime="application/json",
    )
