import os

import pytest
from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import MetadataMode

from fake_api import BASIC_RESULT, TRANSCRIPT_RESULT, URL, FakeAPI, err, ok
from importly import AsyncImportly, Importly, TranscriptionProviderRequiredError
from llama_index.readers.importly import ImportlyReader

URL2 = "https://example.com/podcast/episode-1.mp3"


def fake_api() -> FakeAPI:
    return (
        FakeAPI()
        .on("POST", "/transcribe", ok({"jobId": "t1", "status": "queued", "message": "q"}))
        .on("GET", "/transcribe/status", ok({"jobId": "t1", "status": "running"}), ok({"jobId": "t1", "status": "completed", "result": TRANSCRIPT_RESULT}))
        .on("POST", "/metadata/basic", ok({"jobId": "b1", "status": "queued", "message": "q"}))
        .on("GET", "/metadata/basic/status", ok({"jobId": "b1", "status": "completed", "result": BASIC_RESULT}))
    )


def sync_client(api: FakeAPI) -> Importly:
    return Importly("k", http_client=api.sync_client(), sleep=lambda _: None)


def async_client(api: FakeAPI) -> AsyncImportly:
    async def no_sleep(_):
        return None

    return AsyncImportly("k", http_client=api.async_client(), sleep=no_sleep)


def test_class_contract():
    reader = ImportlyReader(client=sync_client(FakeAPI()))
    assert isinstance(reader, BaseReader)
    assert ImportlyReader.class_name() == "ImportlyReader"
    assert reader.is_remote


def test_api_key_is_not_serialized():
    reader = ImportlyReader(api_key="secret-key", transcript_format="chunks")
    dumped = reader.model_dump() if hasattr(reader, "model_dump") else reader.dict()
    assert "secret-key" not in str(dumped)
    assert dumped["transcript_format"] == "chunks"


def test_text_document():
    [doc] = ImportlyReader(client=sync_client(fake_api())).load_data([URL])
    assert doc.text.startswith("All right")
    assert doc.id_ == f"{URL}#transcript"
    assert doc.metadata["title"] == "Me at the zoo"
    assert doc.metadata["url"] == URL
    assert doc.metadata["duration"] == 19.0
    llm_text = doc.get_content(metadata_mode=MetadataMode.LLM)
    assert "Me at the zoo" in llm_text and "job_id" not in llm_text


def test_chunks_with_timestamps_and_stable_ids():
    docs = ImportlyReader(transcript_format="chunks", chunk_size_seconds=5, client=sync_client(fake_api())).load_data([URL])
    assert [d.metadata["start_seconds"] for d in docs] == [1.2, 7.974]
    assert docs[1].metadata["start_timestamp"] == "00:00:07"
    assert docs[0].id_ == f"{URL}#t=1.200"


def test_single_string_url_and_options():
    api = fake_api()
    ImportlyReader(language="es", provider="importly", include_metadata=False, client=sync_client(api)).load_data(URL2)  # type: ignore[arg-type]
    assert api.json_body(0) == {"url": URL2, "language": "es", "provider": "importly"}
    assert not api.calls("POST", "/metadata/basic")


def test_failure_raises_or_skips():
    api = fake_api()
    api.routes[("GET", "/transcribe/status")] = [ok({"jobId": "t1", "status": "failed", "message": "no captions", "code": "TRANSCRIPTION_PROVIDER_REQUIRED"})]
    with pytest.raises(TranscriptionProviderRequiredError):
        ImportlyReader(client=sync_client(api)).load_data([URL])
    assert ImportlyReader(continue_on_failure=True, client=sync_client(api)).load_data([URL]) == []


def test_bad_start_skipped_with_continue():
    api = fake_api()
    api.routes[("POST", "/transcribe")] = [err(400, "Invalid URL format", "INVALID_URL"), ok({"jobId": "t1", "status": "queued", "message": "q"})]
    docs = ImportlyReader(continue_on_failure=True, client=sync_client(api)).load_data(["bad", URL])
    assert [d.metadata["url"] for d in docs] == [URL]


async def test_aload_data_keeps_order():
    docs = await ImportlyReader(transcript_format="segments", async_client=async_client(fake_api())).aload_data([URL, URL2])
    assert [d.metadata["url"] for d in docs] == [URL] * 4 + [URL2] * 4
    assert docs[2].text == "really really long trunks"


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("IMPORTLY_LIVE_TEST") != "1" or not os.environ.get("IMPORTLY_API_KEY"),
    reason="live test: set IMPORTLY_LIVE_TEST=1 and IMPORTLY_API_KEY",
)
def test_live():
    docs = ImportlyReader(transcript_format="chunks", chunk_size_seconds=30, timeout=300).load_data([os.environ.get("IMPORTLY_LIVE_TEST_URL", URL)])
    assert docs and docs[0].metadata.get("title")
