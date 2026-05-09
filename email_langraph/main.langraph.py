"""LangGraph pipeline: summarise trusted email → Pushover → write summary.md."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

_TOOL_MODULE_NAME = "tool_langraph_impl"


def _load_tool_module():
    path = Path(__file__).resolve().parent / "tool.langraph.py"
    spec = importlib.util.spec_from_file_location(_TOOL_MODULE_NAME, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load tools from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_tools = _load_tool_module()


class EmailInboxState(TypedDict):
    email_body: str
    sender: str
    thread_id: str
    message_id: str
    summary: str


def _node_summarise(state: EmailInboxState) -> dict:
    summary = _tools.summarise_email.invoke({"email_body": state["email_body"]})
    return {"summary": summary}


def _node_notify(state: EmailInboxState) -> dict:
    _tools.notify_trusted_email_received.invoke(
        {
            "sender": state["sender"],
            "summary": state["summary"],
            "thread_id": state["thread_id"],
            "message_id": state["message_id"],
        }
    )
    return {}


def _node_write_file(state: EmailInboxState) -> dict:
    _tools.write_inbox_summary_md.invoke(
        {
            "thread_id": state["thread_id"],
            "message_id": state["message_id"],
            "summary": state["summary"],
        }
    )
    return {}


def build_graph():
    g = StateGraph(EmailInboxState)
    g.add_node("summarise", _node_summarise)
    g.add_node("notify", _node_notify)
    g.add_node("write_inbox", _node_write_file)
    g.add_edge(START, "summarise")
    g.add_edge("summarise", "notify")
    g.add_edge("notify", "write_inbox")
    g.add_edge("write_inbox", END)
    return g.compile()


def run_trusted_email_pipeline(
    email_body: str,
    sender: str,
    thread_id: str,
    message_id: str,
) -> EmailInboxState:
    graph = build_graph()
    initial: EmailInboxState = {
        "email_body": email_body,
        "sender": sender,
        "thread_id": thread_id,
        "message_id": message_id,
        "summary": "",
    }
    final = graph.invoke(initial)
    return final  # type: ignore[return-value]


if __name__ == "__main__":
    demo = run_trusted_email_pipeline(
        email_body="Hi — meeting moved to Monday 10am. Please confirm.",
        sender="boss@example.com",
        thread_id="thread-demo-1",
        message_id="msg-demo-1",
    )
    print("Done. Summary:\n", demo.get("summary"))
