from src.domain.export_models import ExportResult, ProgressEvent, ProgressReporter


def test_export_result_keeps_output_metadata():
    result = ExportResult(
        mode="chat",
        output_dir="E:/exports/chat/sample",
        markdown_files=["E:/exports/chat/sample/chat.md"],
        image_dir="E:/exports/chat/sample/images",
        item_count=1,
    )

    assert result.mode == "chat"
    assert result.output_dir.endswith("sample")
    assert result.item_count == 1


def test_progress_reporter_emits_structured_event():
    received = []

    reporter = ProgressReporter(received.append)
    reporter.info("started")

    assert len(received) == 1
    assert isinstance(received[0], ProgressEvent)
    assert received[0].level == "info"
    assert received[0].message == "started"
