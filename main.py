import os.path
import os
import base64
import importlib.util
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Load environment variables from .env
load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

_run_trusted_email_pipeline = None


def _invoke_trusted_email_pipeline(
    email_body: str, sender: str, thread_id: str, message_id: str
):
    global _run_trusted_email_pipeline
    if _run_trusted_email_pipeline is None:
        path = Path(__file__).resolve().parent / "email_langraph" / "main.langraph.py"
        spec = importlib.util.spec_from_file_location("email_langraph_main", path)
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


def save_file(folder, filename, data, mode='wb'):
    """Helper to write data to a specific folder."""
    path = os.path.join(folder, filename)
    with open(path, mode) as f:
        f.write(data)
    return path

def process_message(service, msg_info):
    """
    Downloads attachments and message body into a thread-specific folder.
    """
    msg_id = msg_info['id']
    thread_id = msg_info['threadId']
    
    # 1. Fetch full message content
    message = service.users().messages().get(userId='me', id=msg_id).execute()
    payload = message.get('payload', {})
    parts = payload.get('parts', [])
    
    # 2. Setup Directory Structure
    thread_dir = os.path.join("downloads", thread_id)
    os.makedirs(thread_dir, exist_ok=True)

    # 3. Handle Multipart logic
    # If no 'parts', the body is directly in the payload (common for simple emails)
    if not parts:
        parts = [payload]

    print(f"📂 Processing Message ID: {msg_id} in Thread: {thread_id}")

    for part in parts:
        filename = part.get('filename')
        mime_type = part.get('mimeType')
        body = part.get('body', {})
        
        # Scenario A: It's an Attachment
        if filename:
            att_id = body.get('attachmentId')
            if att_id:
                attachment = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=att_id
                ).execute()
                data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                save_file(thread_dir, filename, data)
                print(f"  📎 Attachment Saved: {filename}")

        # Scenario B: It's the Message Body (Plain Text)
        elif mime_type == 'text/plain':
            raw_data = body.get('data')
            if raw_data:
                clean_body = base64.urlsafe_b64decode(raw_data.encode('UTF-8')).decode('utf-8')
                save_file(thread_dir, f"body_{msg_id}.txt", clean_body, mode='w')
                print(f"  📝 Message Body Saved.")

    sender, plain_for_ai = plain_text_and_sender_from_message(message)
    if not plain_for_ai:
        plain_for_ai = (
            "(No plain-text body extracted; see downloads folder for HTML or attachments.)"
        )
    try:
        result = _invoke_trusted_email_pipeline(
            plain_for_ai, sender, thread_id, msg_id
        )
        summary = (result.get("summary") or "").strip()
        preview = (summary[:160] + "…") if len(summary) > 160 else summary
        print(f"  🤖 LangGraph: summary / Pushover / ai_inbox. Preview: {preview}")
        
        # 4. Mark as read only AFTER successful processing
        service.users().messages().batchModify(
            userId='me',
            body={'ids': [msg_id], 'removeLabelIds': ['UNREAD']}
        ).execute()
    except Exception as e:
        print(f"  ⚠️ LangGraph pipeline failed: {e}")


def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Get port from .env, default to 8080 for stability
            port = int(os.getenv("PORT", 8080))
            
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            
            # CRITICAL: This must match what you put in Google Cloud Console
            # Use http://localhost:8080/ (with the trailing slash)
            flow.redirect_uri = f'http://localhost:{port}/'
            
            # Use bind_addr to ensure it stays on the local interface
            creds = flow.run_local_server(port=port, host='localhost')
            
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

# Execution logic
service = get_gmail_service()

# 1. Get senders and filter out empty strings
raw_emails = os.getenv("TRUSTED_EMAILS_RECEIVER", "")
allowed_senders = [email.strip() for email in raw_emails.split(",") if email.strip()]

if not allowed_senders:
    print("Error: TRUSTED_EMAILS_RECEIVER is empty in .env")
else:
    # 2. Format query
    sender_query = " OR ".join([f"from:{email}" for email in allowed_senders])
    final_query = f"is:unread ({sender_query})"
    print('final_query: ', final_query)
    # 3. Execute
    results = service.users().messages().list(userId='me', q=final_query).execute()
    messages = results.get('messages', [])

    if not messages:
        print(f"No new messages from: {', '.join(allowed_senders)}")
    else:
        process_message(service, messages[0])