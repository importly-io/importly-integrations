# importly

Turn any video or audio link into files, transcripts and metadata from your Python app.

Send a link from YouTube, TikTok, X, Instagram, a podcast or 1,000+ other sites, and get back the file, a timestamped transcript or the metadata. It works from servers and agent sandboxes, where downloads usually get blocked. Free to try, no card required: [get an API key](https://www.importly.io/login?mode=signup&utm_source=pypi&utm_medium=package&utm_campaign=guerrilla-2026-11).

```bash
pip install importly
export IMPORTLY_API_KEY=...
```

## Transcript

```python
from importly import Importly

client = Importly()  # reads IMPORTLY_API_KEY

transcript = client.transcribe("https://www.youtube.com/watch?v=jNQXAC9IVRw")
print(transcript.text)
for segment in transcript.segments:
    print(segment.start, segment.end, segment.text)

# Group segments into ~2-minute chunks for RAG, each with start/end times
for chunk in transcript.chunks(120):
    print(chunk.start_timestamp, chunk.text[:80])
```

By default the transcript comes from the media's captions. If there are none, `transcribe` raises `TranscriptionProviderRequiredError` with a `quote`; pass `provider="importly"` to use built-in speech-to-text, optionally with `max_cost_dollars`.

## File

```python
result = client.import_media(
    "https://www.tiktok.com/@scout2015/video/6718335390845095173",
    video_quality="720p",
    max_cost_dollars=0.10,
)
print(result.media_url)  # signed download link, valid for 7 days
```

Audio only: `include_video=False`. Copy straight to your own S3-compatible bucket: `store=True` (set up your bucket in the dashboard first).

## Metadata

```python
preview = client.basic_metadata(url)  # title, duration, thumbnail
meta = client.metadata(url)           # description, uploader, stats, formats, ...
print(meta.title, meta.uploader, meta.view_count)
print(meta.raw)                       # every field the source returned
```

## Async

```python
import asyncio
from importly import AsyncImportly

async def main(urls):
    async with AsyncImportly() as client:
        return await asyncio.gather(*(client.transcribe(u) for u in urls))
```

## Webhooks instead of waiting

Every job runs in the background. The one-call helpers above poll until it's done. In a web app, start the job with a `webhook_url` and handle the result when it arrives:

```python
job = client.start_transcription(url, webhook_url="https://your-app.com/webhooks/importly?token=" + WEBHOOK_TOKEN)
save(job.job_id)
```

```python
from importly.webhooks import parse_webhook, token_matches

@app.post("/webhooks/importly")  # Flask
def importly_webhook():
    if not token_matches(request.args.get("token"), WEBHOOK_TOKEN):
        abort(401)
    event = parse_webhook(request.get_data())
    if event.succeeded and event.job_type == "transcribe":
        store_transcript(event.job_id, event.result.text)
    elif event.failed:
        mark_failed(event.job_id, event.code, event.message)
    return "", 204
```

Each job gets one delivery and no retries, so keep a fallback: `client.get_job(job_type, job_id)` returns the job's current state. Webhooks aren't signed; use a secret token in the URL as above, and only act on job ids you started.

You can also do it in steps yourself: `start_import` / `get_import` / `wait_for_import`, and the same for `transcription`, `metadata` and `basic_metadata`.

## Errors

| Exception | When | What to do |
| --- | --- | --- |
| `AuthenticationError` (401) | Missing or wrong API key | Check `IMPORTLY_API_KEY` |
| `InsufficientBalanceError` (402) | Balance too low to start the job (`balance_required`) | Add credits |
| `InvalidURLError` (400, `INVALID_URL`) | The link isn't a valid or supported media URL | Fix the URL |
| `InvalidRequestError` (400) | Another bad parameter | Fix the request |
| `RateLimitError` (429) | Over the hourly limit (`retry_after` seconds) | Retried automatically when the wait is under a minute |
| `InternalServerError` (5xx) | Something broke on Importly's side | Status calls are retried; job starts are not, so they can't start twice |
| `JobFailedError` | The job ran and failed, e.g. `VIDEO_PRIVATE`, `MAX_COST_EXCEEDED` (`.code`, `.documentation_url`) | See the linked page |
| `TranscriptionProviderRequiredError` | No captions and no `provider` (`.quote`) | Retry with `provider="importly"` |
| `JobTimeoutError` | Still running when `timeout` ran out | Poll later or use a webhook |

All of them inherit from `ImportlyError`.

## Pricing

Pay as you go from a credit balance: transcripts from captions and metadata are $0.003 per link, downloads $0.002 per MB (min $0.01). See [pricing](https://www.importly.io/pricing?utm_source=pypi&utm_medium=package&utm_campaign=guerrilla-2026-11).

## Links

- [Docs](https://www.importly.io/docs?utm_source=pypi&utm_medium=package&utm_campaign=guerrilla-2026-11) and [API reference](https://www.importly.io/docs/api-reference?utm_source=pypi&utm_medium=package&utm_campaign=guerrilla-2026-11)
- LangChain: [`langchain-importly`](https://pypi.org/project/langchain-importly/). LlamaIndex: [`llama-index-readers-importly`](https://pypi.org/project/llama-index-readers-importly/)
- Support: support@importly.io

MIT licensed.
