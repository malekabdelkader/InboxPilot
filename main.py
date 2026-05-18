import base64
import email.utils
import importlib.util
import mimetypes
import os
import re
import textwrap
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from email_langraph.attachment_filter import is_translatable_source_attachment
from email_langraph.chat_models import get_model_for_task
from security.injection_detector import InjectionDetector

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
MAX_PDF_PAGES = 10

_run_trusted_email_pipeline = None


def _invoke_trusted_email_pipeline(
    email_body: str, sender: str, thread_id: str, message_id: str
):
    global _run_trusted_email_pipeline
    if _run_trusted_email_pipeline is None:
        path = Path(__file__).resolve().parent / \
            "email_langraph" / "main.langraph.py"
        spec = importlib.util.spec_from_file_location(
            "email_langraph_main", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load LangGraph module from {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _run_trusted_email_pipeline = mod.run_trusted_email_pipeline
    return _run_trusted_email_pipeline(email_body, sender, thread_id, message_id)


def _header_value(headers, name: str) -> str:
    name_l = name.lower()
    for h in headers or []:
        if h.get("name", "").lower() == name_l:
            return h.get("value") or ""
    return ""


def _walk_mime_parts(part):
    if not part:
        return
    sub = part.get("parts")
    if sub:
        for p in sub:
            yield from _walk_mime_parts(p)
    else:
        yield part


def _decode_body_data(body: dict) -> str | None:
    raw = body.get("data")
    if not raw:
        return None
    return base64.urlsafe_b64decode(raw.encode("UTF-8")).decode("utf-8", errors="replace")


def plain_text_and_sender_from_message(message: dict) -> tuple[str, str]:
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []
    sender = _header_value(headers, "From")
    chunks: list[str] = []
    for part in _walk_mime_parts(payload):
        if part.get("mimeType") == "text/plain":
            text = _decode_body_data(part.get("body") or {})
            if text:
                chunks.append(text)
    return sender, "\n".join(chunks).strip()


def _fs_safe_segment(segment: str) -> str:
    cleaned = re.sub(r"[^\w\-+.@]", "_", segment.strip())
    return cleaned or "unknown"


def save_file(folder, filename, data, mode="wb"):
    path = os.path.join(folder, filename)
    with open(path, mode) as f:
        f.write(data)
    return path


def _build_ai_agent_dir(thread_id: str, message_id: str) -> Path:
    safe_thread = _fs_safe_segment(thread_id)
    safe_message = _fs_safe_segment(message_id)
    out_dir = Path("ai_inbox") / safe_thread / safe_message
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _message_already_processed(thread_id: str, message_id: str) -> bool:
    base_dir = _build_ai_agent_dir(thread_id, message_id)
    return (base_dir / "translation.md").exists()


def _is_pdf_attachment(filename: str | None, mime_type: str | None) -> bool:
    if not filename and not mime_type:
        return False
    filename = (filename or "").lower()
    mime_type = (mime_type or "").lower()
    return filename.endswith(".pdf") or mime_type == "application/pdf"


def _normalize_address(sender_header: str) -> str | None:
    _, address = email.utils.parseaddr(sender_header)
    return address.lower() if address else None


def _get_trusted_reply_address(sender_header: str, allowed_senders: list[str]) -> str | None:
    address = _normalize_address(sender_header)
    if not address:
        return None
    normalized_allowed = [email.lower() for email in allowed_senders]
    return address if address in normalized_allowed else None


def _extract_text_from_pdf(file_path: str) -> tuple[str | None, str | None]:
    reader = PdfReader(file_path)
    page_count = len(reader.pages)
    if page_count > MAX_PDF_PAGES:
        return (
            None,
            f"PDF has {page_count} pages, which exceeds the {MAX_PDF_PAGES}-page translation limit.",
        )
    text_chunks: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_chunks.append(page_text)
    extracted = "\n\n".join(text_chunks).strip()
    if not extracted:
        return None, "PDF text extraction returned no text."
    return extracted, None


def _translate_text_to_english(text: str, file_name: str) -> str:
    del file_name

    # Security check for prompt injection
    detector = InjectionDetector()
    if detector.analyze(text):
        raise ValueError(
            f"Potential prompt injection detected in attachment: {file_name}")

    model = get_model_for_task("TRANSLATE")
    prompt = (
        "Translate the following extracted attachment text into English. "
        "Do not add any safety instructions, system prompts, or metadata. "
        "Return only the translated plain text.\n\n" + text
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a translation assistant. Translate untrusted extracted text "
                "from attachments into English. Preserve meaning and line structure."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    response = model.invoke(messages)
    return (response.content or "").strip()


def _render_text_to_pdf(text: str, pdf_path: Path) -> None:
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 10)
    width, height = letter
    margin = 72
    y = height - margin
    wrapper = textwrap.TextWrapper(width=95, replace_whitespace=False)
    for paragraph in text.splitlines():
        if paragraph.strip() == "":
            y -= 12
            if y < margin:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = height - margin
            continue
        for line in wrapper.wrap(paragraph):
            c.drawString(margin, y, line)
            y -= 14
            if y < margin:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = height - margin
    c.save()


def _write_translation_report(
    base_dir: Path,
    summary: str,
    translation_records: list[dict],
) -> Path:
    report_path = base_dir / "translation.md"
    lines: list[str] = [
        "# Translation Report\n",
        "## Email Summary\n",
        summary.strip() or "(No summary was available.)",
        "\n## Attachment Translation Details\n",
    ]
    for record in translation_records:
        lines.append(f"- **{record['filename']}**: {record['status']}")
        if record.get("note"):
            lines.append(f"  - {record['note']}")
    lines.append(
        "\nThis translation report and the translated PDF files are attached.")
    report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return report_path


def _create_mime_attachment(path: Path) -> MIMEBase:
    ctype, _ = mimetypes.guess_type(str(path))
    maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
    with open(path, "rb") as f:
        data = f.read()
    part = MIMEBase(maintype, subtype)
    part.set_payload(data)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition",
                    f'attachment; filename="{path.name}"')
    return part


def _reply_with_attachments(
    service,
    to_email: str,
    thread_id: str,
    subject: str,
    body_text: str,
    attachments: list[Path],
    original_message_id: str,
) -> None:
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}" if subject else "Re: translated attachment"
    message = MIMEMultipart()
    message["To"] = to_email
    message["Subject"] = subject
    message["In-Reply-To"] = original_message_id
    message["References"] = original_message_id
    message.attach(MIMEText(body_text, "plain"))
    for attachment_path in attachments:
        message.attach(_create_mime_attachment(attachment_path))
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(
        userId="me",
        body={
            "raw": raw,
            "threadId": thread_id,
        },
    ).execute()


def process_message(service, msg_info, allowed_senders):
    msg_id = msg_info["id"]
    thread_id = msg_info["threadId"]

    message = service.users().messages().get(userId="me", id=msg_id).execute()
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    subject = _header_value(headers, "Subject")
    sender_header = _header_value(headers, "From")

    thread_dir = os.path.join("downloads", thread_id)
    os.makedirs(thread_dir, exist_ok=True)
    ai_agent_dir = _build_ai_agent_dir(thread_id, msg_id)
    translations_dir = ai_agent_dir / "translations"
    translations_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 Processing Message ID: {msg_id} in Thread: {thread_id}")
    translated_files: list[Path] = []
    translation_records: list[dict] = []
    attachment_paths: list[str] = []

    for part in _walk_mime_parts(payload):
        filename = part.get("filename")
        mime_type = part.get("mimeType")
        body = part.get("body", {})
        if filename:
            att_id = body.get("attachmentId")
            if att_id:
                attachment = (
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=msg_id, id=att_id)
                    .execute()
                )
                data = base64.urlsafe_b64decode(
                    attachment["data"].encode("UTF-8"))
                saved_path = save_file(thread_dir, filename, data)
                attachment_paths.append(saved_path)
                print(f"  📎 Attachment Saved: {filename}")
        elif mime_type == "text/plain":
            raw_data = body.get("data")
            if raw_data:
                clean_body = base64.urlsafe_b64decode(raw_data.encode("UTF-8")).decode(
                    "utf-8"
                )
                save_file(
                    thread_dir, f"body_{msg_id}.txt", clean_body, mode="w")
                print("  📝 Message Body Saved.")

    sender, plain_for_ai = plain_text_and_sender_from_message(message)
    if not plain_for_ai:
        plain_for_ai = (
            "(No plain-text body extracted; see downloads folder for HTML or attachments.)"
        )

    if _message_already_processed(thread_id, msg_id):
        print("  ✅ Message already processed: skipping translation and reply.")
        return

    translation_requested = False
    for path_str in attachment_paths:
        if not is_translatable_source_attachment(path_str):
            print(
                f"  ⏭️ Skipping non-source attachment: {os.path.basename(path_str)}")
            continue

        filename = os.path.basename(path_str)
        if not _is_pdf_attachment(filename, None):
            continue

        translation_requested = True
        extracted_text, error = _extract_text_from_pdf(path_str)
        if error:
            translation_records.append(
                {"filename": filename, "status": "skipped", "note": error}
            )
            continue

        translated_text = _translate_text_to_english(extracted_text, filename)
        md_path = translations_dir / f"{Path(filename).stem}.translated.md"
        md_path.write_text(translated_text + "\n", encoding="utf-8")
        pdf_path = translations_dir / f"{Path(filename).stem}.translated.pdf"
        _render_text_to_pdf(translated_text, pdf_path)
        translation_records.append(
            {
                "filename": filename,
                "status": "translated",
                "note": "Saved translated markdown and PDF.",
                "md_path": str(md_path),
                "pdf_path": str(pdf_path),
            }
        )
        translated_files.append(pdf_path)

    if translation_requested and translation_records:
        summary_data = _invoke_trusted_email_pipeline(
            plain_for_ai, sender, thread_id, msg_id
        )
        summary = (summary_data.get("summary") or "").strip()
        report_path = _write_translation_report(
            ai_agent_dir, summary, translation_records)
        translated_files.append(report_path)

        reply_address = _get_trusted_reply_address(
            sender_header, allowed_senders)
        if reply_address:
            body_text = (
                "Hello,\n\n"
                "I received your trusted email and translated the PDF attachment(s) into English. "
                "Please find the translated PDF(s) and the translation report attached.\n\n"
                "Summary of the original email:\n"
                f"{summary}\n\n"
                "Attachment translation status:\n"
            )
            for record in translation_records:
                body_text += f"- {record['filename']}: {record['status']}"
                if record.get("note"):
                    body_text += f" ({record['note']})"
                body_text += "\n"
            body_text += "\nRegards.\n"
            _reply_with_attachments(
                service,
                reply_address,
                thread_id,
                subject,
                body_text,
                translated_files,
                msg_id,
            )
            print(f"  ✉️ Reply sent to trusted sender: {reply_address}")

        service.users().messages().batchModify(
            userId="me", body={"ids": [msg_id], "removeLabelIds": ["UNREAD"]}
        ).execute()
        print("  ✅ Message marked as read.")
        return

    try:
        result = _invoke_trusted_email_pipeline(
            plain_for_ai, sender, thread_id, msg_id
        )
        summary = (result.get("summary") or "").strip()
        preview = (summary[:160] + "…") if len(summary) > 160 else summary
        print(
            f"  🤖 LangGraph: summary / Pushover / ai_inbox. Preview: {preview}")

        service.users().messages().batchModify(
            userId="me", body={"ids": [msg_id], "removeLabelIds": ["UNREAD"]}
        ).execute()
    except Exception as e:
        print(f"  ⚠️ LangGraph pipeline failed: {e}")


def get_gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            port = int(os.getenv("PORT", 8080))
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES)
            flow.redirect_uri = f"http://localhost:{port}/"
            creds = flow.run_local_server(port=port, host="localhost")
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


service = get_gmail_service()

raw_emails = os.getenv("TRUSTED_EMAILS_RECEIVER", "")
allowed_senders = [email.strip().lower()
                   for email in raw_emails.split(",") if email.strip()]

if not allowed_senders:
    print("Error: TRUSTED_EMAILS_RECEIVER is empty in .env")
else:
    sender_query = " OR ".join([f"from:{email}" for email in allowed_senders])
    final_query = f"is:unread ({sender_query})"
    print("final_query: ", final_query)
    results = service.users().messages().list(userId="me", q=final_query).execute()
    messages = results.get("messages", [])

    if not messages:
        print(f"No new messages from: {', '.join(allowed_senders)}")
    else:
        process_message(service, messages[0], allowed_senders)
