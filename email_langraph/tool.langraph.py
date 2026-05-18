"""LangGraph-related tools: summarise, Pushover notify, inbox markdown file."""

from __future__ import annotations

import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from email_langraph.attachment_filter import is_translatable_source_attachment

load_dotenv()

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_INBOX_ROOT = PROJECT_ROOT / "ai_inbox"
DOWNLOADS_ROOT = PROJECT_ROOT / "downloads"


def _fs_safe_segment(segment: str) -> str:
    cleaned = re.sub(r"[^\w\-+.@]", "_", segment.strip())
    return cleaned or "unknown"


def _summarise_with_mini(email_body: str) -> str:
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    messages = [
        SystemMessage(
            content=(
                "You summarise emails for quick triage. "
                "Return a short plain-text summary: key points, any actions, and dates if present. "
                "Do not add a preamble."
            )
        ),
        HumanMessage(content=email_body),
    ]
    out = model.invoke(messages)
    return (out.content or "").strip()


@tool
def summarise_email(email_body: str) -> str:
    """Summarise the full email body using GPT-4o mini."""
    return _summarise_with_mini(email_body)


@tool
def notify_trusted_email_received(
    sender: str,
    summary: str,
    thread_id: str,
    message_id: str,
) -> str:
    """Send Pushover notification: trusted sender received email, include summary and ids."""
    token = os.getenv("PUSHOVER_TOKEN")
    user = os.getenv("PUSHOVER_USER")
    if not token or not user:
        return "Pushover skipped: PUSHOVER_TOKEN or PUSHOVER_USER not set."

    title = "Trusted sender: new email"
    message = (
        f"From: {sender}\n"
        f"Thread: {thread_id}\n"
        f"Message: {message_id}\n\n"
        f"{summary}"
    )
    resp = requests.post(
        PUSHOVER_URL,
        data={"token": token, "user": user, "title": title, "message": message},
        timeout=30,
    )
    resp.raise_for_status()
    return "Pushover notification sent."


@tool
def write_inbox_summary_md(thread_id: str, message_id: str, summary: str) -> str:
    """Write summary.md under ai_inbox/<thread_id>/<message_id>/."""
    t = _fs_safe_segment(thread_id)
    m = _fs_safe_segment(message_id)
    out_dir = AI_INBOX_ROOT / t / m
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary.md"
    path.write_text(summary.strip() + "\n", encoding="utf-8")
    return str(path)


@tool
def check_for_attachments(thread_id: str, message_id: str) -> list[str]:
    """List translatable source attachments in downloads/<thread_id>/ (excludes system outputs)."""
    del message_id  # downloads are stored per thread
    t = _fs_safe_segment(thread_id)
    target_dir = DOWNLOADS_ROOT / t
    if not target_dir.exists():
        return []
    return [
        str(f)
        for f in target_dir.iterdir()
        if f.is_file() and is_translatable_source_attachment(f)
    ]


def all_tools():
    return [
        summarise_email,
        notify_trusted_email_received,
        write_inbox_summary_md,
        check_for_attachments,
    ]
