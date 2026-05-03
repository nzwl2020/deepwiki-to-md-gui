from src.domain.export_models import (
    CancellationToken,
    ExportOptions,
    ExportResult,
    ExportTask,
    ProgressEvent,
    ProgressReporter,
)


def test_export_result_keeps_output_metadata():
    result = ExportResult(
        mode="chat",
        source_url="https://deepwiki.com/search/sample",
        output_dir="E:/exports/chat/sample",
        markdown_files=["E:/exports/chat/sample/chat.md"],
        image_dir="E:/exports/chat/sample/images",
        item_count=1,
        preferred_markdown_file="E:/exports/chat/sample/chat.md",
    )

    assert result.mode == "chat"
    assert result.source_url.endswith("/sample")
    assert result.output_dir.endswith("sample")
    assert result.item_count == 1
    assert result.primary_markdown_file.endswith("chat.md")


def test_progress_reporter_emits_structured_event():
    received = []

    reporter = ProgressReporter(received.append)
    reporter.info("started")

    assert len(received) == 1
    assert isinstance(received[0], ProgressEvent)
    assert received[0].level == "info"
    assert received[0].message == "started"


def test_progress_reporter_child_inherits_context():
    received = []

    reporter = ProgressReporter(received.append)
    child = reporter.child(task_index=2, task_total=5)
    child.info("running", stage="export", item_current=3, item_total=7)

    assert received[0].task_index == 2
    assert received[0].task_total == 5
    assert received[0].stage == "export"
    assert received[0].item_current == 3
    assert received[0].item_total == 7


def test_cancellation_token_raises_after_cancel():
    token = CancellationToken()
    token.cancel()

    try:
        token.raise_if_cancelled()
    except RuntimeError as exc:
        assert str(exc) == "Export canceled by user."
    else:
        raise AssertionError("Expected cancellation to raise an error.")


def test_export_task_keeps_options_and_page_filter():
    options = ExportOptions(
        incremental_export=True,
        generate_merged_wiki=True,
        include_code_references=False,
    )
    task = ExportTask(
        url="https://deepwiki.com/langchain-ai/langchain",
        output_dir="E:/exports",
        options=options,
        selected_wiki_page_urls=("https://deepwiki.com/langchain-ai/langchain/page-a",),
    )

    assert task.options.incremental_export is True
    assert task.options.generate_merged_wiki is True
    assert task.options.include_code_references is False
    assert task.has_page_selection is True
