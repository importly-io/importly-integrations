import pytest

from fake_api import BASIC_RESULT, IMPORT_RESULT, TRANSCRIPT_RESULT, URL, FakeAPI, err, ok
from importly import (
    APIConnectionError,
    AsyncImportly,
    AuthenticationError,
    Importly,
    InsufficientBalanceError,
    InternalServerError,
    InvalidRequestError,
    InvalidURLError,
    JobFailedError,
    JobTimeoutError,
    MissingAPIKeyError,
    NotFoundError,
    RateLimitError,
    TranscriptionProviderRequiredError,
)

JOB = "95be812f-4a2c-410a-9fcb-3ca5b445cc44"


def make(api: FakeAPI, **kwargs) -> Importly:
    sleeps = []
    client = Importly("test-key", http_client=api.sync_client(), sleep=sleeps.append, **kwargs)
    client.sleeps = sleeps  # type: ignore[attr-defined]
    return client


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("IMPORTLY_API_KEY", "env-key")
    api = FakeAPI().on("GET", "/balance", ok({"balance": 2.97, "currency": "USD"}))
    client = Importly(http_client=api.sync_client())
    assert client.balance().balance == 2.97
    assert api.requests[0].headers["Authorization"] == "Bearer env-key"
    assert api.requests[0].headers["User-Agent"].startswith("importly-python/")
    assert str(api.requests[0].url) == "https://api.importly.io/balance"


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("IMPORTLY_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        Importly()


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("IMPORTLY_BASE_URL", "http://localhost:8080/")
    api = FakeAPI().on("GET", "/balance", ok({"balance": 1, "currency": "USD"}))
    make(api).balance()
    assert str(api.requests[0].url) == "http://localhost:8080/balance"


def test_transcribe_starts_polls_and_returns_typed_transcript():
    api = (
        FakeAPI()
        .on("POST", "/transcribe", ok({"jobId": JOB, "status": "queued", "message": "queued"}))
        .on(
            "GET",
            "/transcribe/status",
            ok({"jobId": JOB, "status": "queued"}),
            ok({"jobId": JOB, "status": "running"}),
            ok({"jobId": JOB, "status": "completed", "result": TRANSCRIPT_RESULT}),
        )
    )
    client = make(api)
    transcript = client.transcribe(URL, language="en", poll_interval=2)
    assert api.json_body(0) == {"url": URL, "language": "en"}
    assert api.requests[1].url.params["id"] == JOB
    assert transcript.source == "platform_captions"
    assert transcript.duration == 19.0
    assert transcript.segments[0].start == 1.2
    assert transcript.segments[2].text == "really really long trunks"
    assert transcript.cost_in_dollars == 0.003
    assert client.sleeps == [2, 2]


def test_import_body_uses_api_field_names_and_skips_none():
    api = (
        FakeAPI()
        .on("POST", "/import", ok({"jobId": JOB, "status": "queued", "message": "q"}))
        .on("GET", "/import/status", ok({"jobId": JOB, "status": "completed", "result": {**IMPORT_RESULT, "transcript": {"status": "skipped", "reason": "no captions", "costInDollars": 0}}}))
    )
    result = make(api).import_media(
        URL,
        include_video=False,
        audio_quality="high",
        max_cost_dollars=0.05,
        webhook_url=None,
        include_transcript=True,
        store=True,
        storage_path="videos/2026",
    )
    assert api.json_body(0) == {
        "url": URL,
        "includeVideo": False,
        "audioQuality": "high",
        "maxCostDollars": 0.05,
        "includeTranscript": True,
        "store": True,
        "storagePath": "videos/2026",
    }
    assert result.media_url.startswith("https://storage.example/")
    assert result.file_size_bytes == 120621
    assert result.transcript is None
    assert result.transcript_skipped_reason == "no captions"


def test_unknown_option_is_a_type_error():
    with pytest.raises(TypeError, match="videoQuality"):
        make(FakeAPI()).start_import(URL, videoQuality="720p")


def test_basic_metadata_and_metadata():
    api = (
        FakeAPI()
        .on("POST", "/metadata/basic", ok({"jobId": "b1", "status": "queued", "message": "q"}))
        .on("GET", "/metadata/basic/status", ok({"jobId": "b1", "status": "completed", "result": BASIC_RESULT}))
        .on("POST", "/metadata", ok({"jobId": "m1", "status": "queued", "message": "q"}))
        .on("GET", "/metadata/status", ok({"jobId": "m1", "status": "completed", "result": {"id": "jNQXAC9IVRw", "title": "Me at the zoo", "uploader": "jawed", "view_count": 448211510, "formats": [{"format_id": "140"}], "chapters": []}}))
    )
    client = make(api)
    basic = client.basic_metadata(URL)
    assert (basic.title, basic.duration) == ("Me at the zoo", 19.0)
    meta = client.metadata(URL)
    assert meta.uploader == "jawed"
    assert meta.view_count == 448211510
    assert meta.formats[0]["format_id"] == "140"
    assert "chapters" in meta.raw


def test_start_with_webhook_returns_job_id_only():
    api = FakeAPI().on("POST", "/metadata/basic", ok({"jobId": "b1", "status": "queued", "message": "q"}))
    job = make(api).start_basic_metadata(URL, webhook_url="https://app.example/hook?token=t")
    assert job.job_id == "b1"
    assert api.json_body(0)["webhookUrl"] == "https://app.example/hook?token=t"


def test_failed_job_raises_with_code_and_docs_link():
    api = (
        FakeAPI()
        .on("POST", "/import", ok({"jobId": JOB, "status": "queued", "message": "q"}))
        .on("GET", "/import/status", ok({"jobId": JOB, "status": "failed", "message": "Source video is unavailable.", "code": "VIDEO_UNAVAILABLE", "documentationUrl": "https://www.importly.io/docs/errors/media-unavailable"}))
    )
    with pytest.raises(JobFailedError) as info:
        make(api).import_media(URL)
    assert info.value.code == "VIDEO_UNAVAILABLE"
    assert info.value.job_id == JOB
    assert "media-unavailable" in str(info.value)


def test_transcription_provider_required_carries_quote():
    quote = {"provider": "importly", "estimatedMinutes": 12, "estimatedCostDollars": 0.12}
    api = (
        FakeAPI()
        .on("POST", "/transcribe", ok({"jobId": JOB, "status": "queued", "message": "q"}))
        .on("GET", "/transcribe/status", ok({"jobId": JOB, "status": "failed", "message": "This video has no captions.", "code": "TRANSCRIPTION_PROVIDER_REQUIRED", "quote": quote}))
    )
    with pytest.raises(TranscriptionProviderRequiredError) as info:
        make(api).transcribe(URL)
    assert info.value.quote == quote


def test_get_job_returns_status_without_raising_on_failure():
    api = FakeAPI().on("GET", "/metadata/status", ok({"jobId": "m1", "status": "failed", "message": "private", "code": "VIDEO_PRIVATE"}))
    status = make(api).get_metadata("m1")
    assert status.failed and status.is_done and status.code == "VIDEO_PRIVATE"
    assert status.result is None


def test_wait_times_out():
    api = FakeAPI().on("GET", "/transcribe/status", ok({"jobId": JOB, "status": "running"}))
    with pytest.raises(JobTimeoutError) as info:
        make(api).wait_for_transcription(JOB, timeout=1, poll_interval=5)
    assert info.value.job_id == JOB


@pytest.mark.parametrize(
    "status,body,error_type",
    [
        (401, {"success": False, "error": "Invalid API key", "code": "UNAUTHORIZED"}, AuthenticationError),
        (402, {"success": False, "error": "Insufficient balance.", "code": "INSUFFICIENT_BALANCE", "endpoint": "/import", "balanceRequired": 0.01}, InsufficientBalanceError),
        (400, {"success": False, "error": "Invalid URL format", "code": "INVALID_URL"}, InvalidURLError),
        (400, {"success": False, "error": "Webhook URL must use HTTPS", "code": "INVALID_REQUEST"}, InvalidRequestError),
        (400, {"success": False, "error": "maxCostDollars must be a positive number"}, InvalidRequestError),
        (404, {"success": False, "error": "Import job not found", "code": "NOT_FOUND"}, NotFoundError),
    ],
)
def test_request_errors_map_to_types(status, body, error_type):
    api = FakeAPI().on("POST", "/import", (status, body))
    with pytest.raises(error_type) as info:
        make(api).start_import(URL)
    assert info.value.status_code == status
    assert len(api.requests) == 1  # never retried


def test_insufficient_balance_details():
    api = FakeAPI().on("POST", "/transcribe", err(402, "Insufficient balance.", "INSUFFICIENT_BALANCE", endpoint="/transcribe", balanceRequired=0.01))
    with pytest.raises(InsufficientBalanceError) as info:
        make(api).start_transcription(URL)
    assert info.value.balance_required == 0.01
    assert info.value.endpoint == "/transcribe"


def test_rate_limit_is_retried_after_retry_after():
    api = (
        FakeAPI()
        .on("POST", "/metadata/basic", err(429, "Rate limit exceeded", "RATE_LIMITED", retryAfter=3, limit=1000, remaining=0), ok({"jobId": "b1", "status": "queued", "message": "q"}))
    )
    client = make(api)
    assert client.start_basic_metadata(URL).job_id == "b1"
    assert client.sleeps == [3.0]


def test_rate_limit_with_long_wait_raises():
    api = FakeAPI().on("POST", "/import", err(429, "Rate limit exceeded", "RATE_LIMITED", retryAfter=1800, limit=240))
    with pytest.raises(RateLimitError) as info:
        make(api).start_import(URL)
    assert info.value.retry_after == 1800
    assert info.value.limit == 240
    assert len(api.requests) == 1


def test_server_error_retried_for_get_not_post():
    api = (
        FakeAPI()
        .on("GET", "/balance", err(500, "Internal server error", "INTERNAL_ERROR"), ok({"balance": 1.5, "currency": "USD"}))
        .on("POST", "/import", err(500, "Internal server error", "INTERNAL_ERROR"))
    )
    client = make(api)
    assert client.balance().balance == 1.5
    with pytest.raises(InternalServerError):
        client.start_import(URL)
    assert len(api.calls("POST", "/import")) == 1


def test_connection_error_becomes_api_connection_error():
    import httpx

    api = FakeAPI().on("GET", "/balance", (0, httpx.ReadError("reset")))
    client = make(api, max_retries=1)
    with pytest.raises(APIConnectionError):
        client.balance()
    assert len(api.requests) == 2


async def test_async_client_transcribe():
    api = (
        FakeAPI()
        .on("POST", "/transcribe", ok({"jobId": JOB, "status": "queued", "message": "q"}))
        .on("GET", "/transcribe/status", ok({"jobId": JOB, "status": "running"}), ok({"jobId": JOB, "status": "completed", "result": TRANSCRIPT_RESULT}))
    )
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    async with AsyncImportly("k", http_client=api.async_client(), sleep=fake_sleep) as client:
        transcript = await client.transcribe(URL, provider="importly", max_cost_dollars=0.5)
    assert api.json_body(0) == {"url": URL, "provider": "importly", "maxCostDollars": 0.5}
    assert transcript.language == "en"
    assert sleeps == [3.0]


async def test_async_errors():
    api = FakeAPI().on("POST", "/import", err(401, "Invalid API key", "UNAUTHORIZED"))
    client = AsyncImportly("k", http_client=api.async_client())
    with pytest.raises(AuthenticationError):
        await client.start_import(URL)
