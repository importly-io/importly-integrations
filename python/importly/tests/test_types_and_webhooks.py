import json

import pytest

from fake_api import TRANSCRIPT_RESULT
from importly import (
    BasicMetadata,
    ImportResult,
    InvalidWebhookError,
    JobFailedError,
    Transcript,
    format_timestamp,
    parse_webhook,
    token_matches,
)


def test_chunks_group_segments_by_window_without_splitting():
    transcript = Transcript.from_dict(TRANSCRIPT_RESULT)
    chunks = transcript.chunks(5)
    assert [(c.start, c.end) for c in chunks] == [(1.2, 7.974), (7.974, 14.367)]
    assert chunks[0].text.startswith("All right")
    assert chunks[1].start_timestamp == "00:00:07"
    assert [c.index for c in chunks] == [0, 1]


def test_chunks_without_segments_returns_whole_text():
    transcript = Transcript.from_dict({"text": "hello", "source": "importly", "duration": 75})
    [chunk] = transcript.chunks(30)
    assert (chunk.text, chunk.start, chunk.end) == ("hello", 0.0, 75.0)
    assert Transcript.from_dict({"text": "", "source": "importly"}).chunks() == []
    with pytest.raises(ValueError):
        transcript.chunks(0)


def test_format_timestamp():
    assert format_timestamp(3725.9) == "01:02:05"


def test_parse_transcribe_webhook_from_bytes():
    body = {"success": True, "data": {"jobId": "j1", "type": "transcribe", "status": "completed", **TRANSCRIPT_RESULT}}
    event = parse_webhook(json.dumps(body).encode())
    assert event.succeeded and event.job_type == "transcribe"
    assert isinstance(event.result, Transcript)
    assert len(event.result.segments) == 4


def test_parse_import_webhook_with_s3():
    body = {
        "success": True,
        "data": {
            "jobId": "j2",
            "type": "import",
            "status": "completed",
            "mediaUrl": "https://storage.example/x.mp4",
            "title": "Me at the zoo",
            "s3Storage": {"url": "https://bucket.s3/videos/zoo.mp4", "bucket": "bucket", "key": "videos/zoo.mp4"},
        },
    }
    event = parse_webhook(body)
    assert isinstance(event.result, ImportResult)
    assert event.result.s3_storage.key == "videos/zoo.mp4"


def test_parse_basic_metadata_webhook():
    body = {"success": True, "data": {"jobId": "j3", "type": "basic-metadata", "status": "completed", "title": "T", "duration": 5, "thumbnail": None}}
    event = parse_webhook(json.dumps(body))
    assert isinstance(event.result, BasicMetadata) and event.result.title == "T"


def test_parse_failed_webhook():
    body = {"success": False, "data": {"jobId": "j4", "type": "basic-metadata", "status": "failed", "code": "INVALID_URL", "message": "Invalid or unsupported URL."}}
    event = parse_webhook(body)
    assert event.failed and event.result is None
    assert event.code == "INVALID_URL"
    error = event.to_error()
    assert isinstance(error, JobFailedError) and error.job_id == "j4"


@pytest.mark.parametrize("payload", [b"not json", {"success": True}, {"data": {"jobId": "x"}}, {"data": {"jobId": "x", "type": "nope", "status": "completed"}}])
def test_invalid_webhooks(payload):
    with pytest.raises(InvalidWebhookError):
        parse_webhook(payload)


def test_token_matches():
    assert token_matches("abc", "abc")
    assert not token_matches("abd", "abc")
    assert not token_matches(None, "abc")
    assert not token_matches("abc", "")
