# TODO - Migouda AI

This file tracks implementation work and technical cleanup tasks.

## Priority 0 - Foundations

- [ ] Enforce English-first policy across all outputs (summaries, translations, notifications).
- [ ] Implement prompt-injection safety policy for untrusted email/body/attachment content.
- [ ] Add processing ledger to detect already processed `message_id` and prevent duplicate execution.
- [ ] Add thread-level memory to skip already translated files and process only new files.

## Priority 1 - Action engine

- [ ] Implement action keyword parser for `_NOTIFY`, `_TRANSLATE`, `_SUMMARIZE`, and extensible `_...` actions.
- [ ] Enforce MUST-DO execution for detected keywords.
- [ ] Implement fallback decision behavior when no keyword is present or keyword set is incomplete/unclear.

## Priority 2 - Translation pipeline

- [ ] Implement attachment classifier for translatable text-like files.
- [ ] Implement PDF text extraction via Python library (no raw PDF to LLM).
- [ ] Enforce PDF >10 page cancellation with explicit English notification.
- [ ] Implement translation output saving to `ai_agent/<thread_id>/<message_id>/translations/`.
- [ ] Add short English summary per translated file.

## Priority 3 - Reply workflow

- [ ] Implement in-thread Gmail reply with translated files as attachments.
- [ ] Include English execution report in reply (actions taken, skipped actions, reasons).

## Priority 4 - Context + validator

- [ ] Add runtime agent context file (purpose, role, user profile, constraints, safety rules).
- [ ] Implement validator stage with reject-only behavior (no retries).
- [ ] On validation failure, stop request, notify rejection reason, and persist rejection report in message folder.

## Priority 5 - Professional cleanup (new)

- [ ] Redesign project folder layout to a clean, production-style architecture.
- [ ] Split responsibilities into clear modules (ingestion, parsing, actions, translation, reply, validation, notifications, persistence).
- [ ] Replace dynamic module loading where unnecessary with explicit package/module imports.
- [ ] Introduce typed data models for message state, action plan, validation report, and processing ledger entries.
- [ ] Standardize naming conventions (files, folders, symbols) and fix typos (`translate`, `summarize`, etc.).
- [ ] Add centralized config/env management with validation and defaults.
- [ ] Add structured logging and error taxonomy (recoverable vs fatal).
- [ ] Add tests for idempotency, keyword routing, translation guardrails, and validator rejection behavior.
- [ ] Add developer docs: architecture overview, runbook, and contribution standards.

## Notes

- Update this file whenever scope changes.
- Keep `claude.md` synchronized with implementation status and behavior requirements.
