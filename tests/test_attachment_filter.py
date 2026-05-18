from pathlib import Path

from email_langraph.attachment_filter import is_translatable_source_attachment


def test_skips_system_outputs():
    assert not is_translatable_source_attachment("summary.md")
    assert not is_translatable_source_attachment("translated.md")
    assert not is_translatable_source_attachment("translation.md")
    assert not is_translatable_source_attachment("report.translated.pdf")
    assert not is_translatable_source_attachment("translated-invoice.pdf")


def test_allows_source_documents():
    assert is_translatable_source_attachment("contract.pdf")
    assert is_translatable_source_attachment("notes.txt")
    assert is_translatable_source_attachment("brief.md")


def test_skips_paths_under_output_folders():
    path = Path("ai_inbox/thread1/msg1/summary.md")
    assert not is_translatable_source_attachment(path)
    path = Path("downloads/thread1/translations/foo.pdf")
    assert not is_translatable_source_attachment(path)
