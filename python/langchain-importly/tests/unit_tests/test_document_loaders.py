import logging

import pytest
from langchain_core.document_loaders import BaseLoader

from fake_api import BASIC_RESULT, TRANSCRIPT_RESULT, URL, FakeAPI, err, ok
from importly import AsyncImportly, Importly, InvalidURLError, TranscriptionProviderRequiredError
from langchain_importly import ImportlyLoader

URL2 = "https://example.com/podcast/episode-1.mp3"


def fake_api(*, transcribe_status=None) -> FakeAPI:
    return (
        FakeAPI()
        .on("POST", "/transcribe", ok({"jobId": "t1", "status": "queued", "message": "q"}))
        .on("GET", "/transcribe/status", *(transcribe_status or [ok({"jobId": "t1", "status": "running"}), ok({"jobId": "t1", "status": "completed", "result": TRANSCRIPT_RESULT})]))
        .on("POST", "/metadata/basic", ok({"jobId": "b1", "status": "queued", "message": "q"}))
        .on("GET", "/metadata/basic/status", ok({"jobId": "b1", "status": "completed", "result": BASIC_RESULT}))
    )


def sync_client(api: FakeAPI) -> Importly:
    return Importly("k", http_client=api.sync_client(), sleep=lambda _: None)


def async_client(api: FakeAPI) -> AsyncImportly:
    async def no_sleep(_):
        return None

    return AsyncImportly("k", http_client=api.async_client(), sleep=no_sleep)


def test_is_a_langchain_loader():
    assert isinstance(ImportlyLoader(URL, client=sync_client(FakeAPI())), BaseLoader)


def test_text_format_one_document_with_metadata():
    api = fake_api()
    docs = ImportlyLoader(URL, client=sync_client(api)).load()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.page_content.startswith("All right, so here we are")
    assert doc.metadata == {
        "source": URL,
        "url": URL,
        "job_id": "t1",
        "language": "en",
        "transcript_source": "platform_captions",
        "duration": 19.0,
        "title": "Me at the zoo",
        "thumbnail": "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg",
    }
    assert api.json_body(0) == {"url": URL}


def test_chunks_carry_timestamps():
    docs = ImportlyLoader(URL, transcript_format="chunks", chunk_size_seconds=5, client=sync_client(fake_api())).load()
    assert len(docs) == 2
    assert docs[0].metadata["start_seconds"] == 1.2
    assert docs[0].metadata["end_seconds"] == 7.974
    assert docs[1].metadata["start_timestamp"] == "00:00:07"
    assert docs[1].metadata["chunk_index"] == 1
    assert docs[1].metadata["title"] == "Me at the zoo"


def test_segments_format():
    docs = ImportlyLoader(URL, transcript_format="segments", client=sync_client(fake_api())).load()
    assert [d.page_content for d in docs][2] == "really really long trunks"
    assert docs[3].metadata["end_seconds"] == 14.367


def test_options_are_sent_and_metadata_can_be_skipped():
    api = fake_api()
    ImportlyLoader([URL2], language="es", provider="importly", max_cost_dollars=0.5, include_metadata=False, client=sync_client(api)).load()
    assert api.json_body(0) == {"url": URL2, "language": "es", "provider": "importly", "maxCostDollars": 0.5}
    assert not api.calls("POST", "/metadata/basic")


def test_jobs_for_all_links_start_before_waiting():
    api = fake_api()
    ImportlyLoader([URL, URL2], client=sync_client(api)).load()
    posts = [r.url.path for r in api.requests if r.method == "POST"]
    first_poll = next(i for i, r in enumerate(api.requests) if r.method == "GET")
    assert posts == ["/transcribe", "/metadata/basic", "/transcribe", "/metadata/basic"]
    assert first_poll == 4


def test_failure_raises_by_default():
    api = fake_api(transcribe_status=[ok({"jobId": "t1", "status": "failed", "message": "no captions", "code": "TRANSCRIPTION_PROVIDER_REQUIRED"})])
    with pytest.raises(TranscriptionProviderRequiredError):
        ImportlyLoader(URL, client=sync_client(api)).load()


def test_continue_on_failure_skips_bad_links(caplog):
    api = fake_api()
    api.routes[("POST", "/transcribe")] = [err(400, "Invalid URL format", "INVALID_URL"), ok({"jobId": "t1", "status": "queued", "message": "q"})]
    with caplog.at_level(logging.WARNING):
        docs = ImportlyLoader(["not a url", URL], continue_on_failure=True, client=sync_client(api)).load()
    assert len(docs) == 1 and docs[0].metadata["source"] == URL
    assert "not a url" in caplog.text


def test_invalid_url_raises_without_continue():
    api = fake_api()
    api.routes[("POST", "/transcribe")] = [err(400, "Invalid URL format", "INVALID_URL")]
    with pytest.raises(InvalidURLError):
        ImportlyLoader("nope", client=sync_client(api)).load()


def test_metadata_failure_does_not_fail_the_document():
    api = fake_api()
    api.routes[("GET", "/metadata/basic/status")] = [ok({"jobId": "b1", "status": "failed", "message": "x", "code": "VIDEO_UNAVAILABLE"})]
    [doc] = ImportlyLoader(URL, client=sync_client(api)).load()
    assert "title" not in doc.metadata
    assert doc.metadata["duration"] == 19.0


def test_bad_arguments():
    with pytest.raises(ValueError):
        ImportlyLoader(URL, transcript_format="lines", client=sync_client(FakeAPI()))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ImportlyLoader(URL, chunk_size_seconds=0, client=sync_client(FakeAPI()))


async def test_async_load_keeps_order():
    api = fake_api()
    loader = ImportlyLoader([URL, URL2], transcript_format="chunks", chunk_size_seconds=5, async_client=async_client(api))
    docs = await loader.aload()
    assert [d.metadata["source"] for d in docs] == [URL, URL, URL2, URL2]
    assert docs[0].metadata["title"] == "Me at the zoo"


async def test_async_continue_on_failure():
    api = fake_api()
    api.routes[("POST", "/transcribe")] = [err(400, "Invalid URL format", "INVALID_URL"), ok({"jobId": "t1", "status": "queued", "message": "q"})]
    loader = ImportlyLoader(["bad", URL], continue_on_failure=True, max_concurrency=1, async_client=async_client(api))
    docs = [d async for d in loader.alazy_load()]
    assert len(docs) == 1
