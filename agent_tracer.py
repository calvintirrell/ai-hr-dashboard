"""
Agent trace utilities.

build_agent_trace(result) -> list[dict]
    Returns structured step records that can be rendered in any UI (Streamlit,
    web, etc.) or printed to stdout.

print_agent_trace(result) -> None
    CLI pretty-printer. Thin wrapper around build_agent_trace.

Adapted from https://github.com/daveebbelaar/ai-cookbook/blob/main/agents/agent-complexity/utils.py
"""

from pydantic_ai.messages import ModelResponse, ModelRequest


def build_agent_trace(result) -> list[dict]:
    """Walk the run's messages and return a flat list of trace records.

    Each record is one of:
      {"step": int, "type": "tool_call",      "tool_name": str, "args": Any}
      {"step": int, "type": "tool_return",    "tool_name": str, "content": str}
      {"step": int, "type": "final_response", "content": str}

    Tool-return records share the step number of the preceding tool_call.
    """
    records: list[dict] = []
    step = 0
    for message in result.all_messages():
        if isinstance(message, ModelResponse):
            for part in message.parts:
                part_type = type(part).__name__
                if part_type == "ToolCallPart":
                    step += 1
                    records.append({
                        "step": step,
                        "type": "tool_call",
                        "tool_name": part.tool_name,
                        "args": part.args,
                    })
                elif part_type == "TextPart":
                    step += 1
                    records.append({
                        "step": step,
                        "type": "final_response",
                        "content": part.content,
                    })
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                part_type = type(part).__name__
                if part_type == "ToolReturnPart":
                    records.append({
                        "step": step,
                        "type": "tool_return",
                        "tool_name": part.tool_name,
                        "content": str(part.content),
                    })
    return records


def print_agent_trace(result) -> None:
    """CLI pretty-printer. Renders the same trace shape as the prior version."""
    print("\n" + "=" * 60)
    print("AGENT TRACER")
    print("=" * 60)

    for rec in build_agent_trace(result):
        if rec["type"] == "tool_call":
            print(f"\n[Step {rec['step']}] Tool call: {rec['tool_name']}")
            print(f"         Args: {rec['args']}")
        elif rec["type"] == "final_response":
            print(f"\n[Step {rec['step']}] Final response")
            print(f"         {rec['content'][:200]}")
        elif rec["type"] == "tool_return":
            print(f"         <- {rec['tool_name']} returned: {rec['content'][:150]}")

    print("\n" + "=" * 60)
