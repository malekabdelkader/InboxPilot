# Email LangGraph Pipeline

An automated email processing pipeline built with LangGraph, designed to process (translate,summarise,store attachements) incoming emails from trusted senders.

## Overview

This project implements a stateful graph workflow that intercepts email data, processes it using LLMs, and executes a series of automated tasks. It is designed to help users triage important communications without manually reading through every thread.

## Key Features

- **Intelligent Summarization**: Utilizes `gpt-4o-mini` to extract key points, action items, and important dates from email bodies, providing a quick-glance summary.
- **Push Notifications**: Integrated with **Pushover** to send real-time mobile alerts containing the email summary and metadata (sender, thread ID) whenever a trusted email is detected.
- **Structured Inbox Archive**: Automatically maintains an organized local archive of email summaries in a structured Markdown format:
  `ai_inbox/<thread_id>/<message_id>/summary.md`
- **Attachment Awareness**: Includes utility tools to scan and identify translatable source attachments within a dedicated downloads directory.

## Workflow

The LangGraph pipeline follows these steps:

1. **Summarize**: The email body is sent to the LLM for summarization.
2. **Notify**: A notification is dispatched via Pushover.
3. **Write**: The generated summary is persisted to the file system for long-term tracking.

### Prerequisites

- Python 3.11+
- OpenAI API Key
- Pushover User Key and API Token (for notifications)
- Google Cloud Project with Gmail API enabled
- Google OAuth2 Credentials (`credentials.json`) with Gmail read access

````

### 2. Update the "Setup" section:

```markdown
## Setup

1. Clone the repository.
2. Install dependencies:
   ```bash
   uv sync
````

3. Configure your environment variables in a `.env` file:
   ```env
   OPENAI_API_KEY=your_openai_key
   PUSHOVER_USER=your_pushover_user_key
   PUSHOVER_TOKEN=your_pushover_api_token
   ```
4. **Google OAuth2 Configuration**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a new project (or select an existing one).
   - Enable the **Gmail API**.
   - Configure the **OAuth consent screen** (set user type to 'External' and add your email as a test user).
   - Navigate to **Credentials** -> **Create Credentials** -> **OAuth client ID**.
   - Select **Web App** as the application type.
   - Download the JSON content and save it as `credentials.json` in the root directory of this project.
5. Run:
   ```bash
   uv run main.py
   ```
