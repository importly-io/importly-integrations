# LlamaIndex Readers Integration: Importly

```bash
pip install llama-index-readers-importly
export IMPORTLY_API_KEY=...   # https://www.importly.io/login?mode=signup&utm_source=llamaindex&utm_medium=package&utm_campaign=guerrilla-2026-11
```

`ImportlyReader` turns video and audio links into transcript `Document`s: YouTube, TikTok, X, Instagram, podcasts and 1,000+ other sites. Each Document carries the title, duration, URL and, when chunked, the start and end time of its part of the video.

It runs on the [Importly API](https://www.importly.io/?utm_source=llamaindex&utm_medium=package&utm_campaign=guerrilla-2026-11), so it keeps working once your app is deployed: from servers, serverless functions and agent sandboxes, where video sites usually block downloads. Free to try, no card required.

## Usage

```python
from llama_index.core import VectorStoreIndex
from llama_index.readers.importly import ImportlyReader

reader = ImportlyReader(transcript_format="chunks", chunk_size_seconds=60)
documents = reader.load_data(
    [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://www.tiktok.com/@scout2015/video/6718335390845095173",
    ]
)
# async: documents = await reader.aload_data([...])

index = VectorStoreIndex.from_documents(documents)
response = index.as_query_engine().query("What does he say about the elephants?")
for node in response.source_nodes:
    print(node.metadata["title"], node.metadata["start_timestamp"])
```

Document metadata: `url`, `title`, `duration`, `language`, `thumbnail`, `transcript_source`, `job_id`, and for `"chunks"` / `"segments"` also `chunk_index`, `start_seconds`, `end_seconds`, `start_timestamp`, `end_timestamp`. Ids are stable (`<url>#t=<start>`), so re-loading a link updates the same nodes. Bookkeeping keys are excluded from what the LLM and the embedding model see.

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `transcript_format` | `"text"` | `"text"` (one Document per link), `"chunks"` (~`chunk_size_seconds` windows) or `"segments"` |
| `chunk_size_seconds` | `120` | Window length for `"chunks"`; segments are never split |
| `language` | captions' default | Two-letter code, e.g. `"es"` |
| `provider` | `None` | `"importly"` turns on speech-to-text for media without captions (billed per minute) |
| `max_cost_dollars` | `None` | Cap per link for speech-to-text |
| `include_metadata` | `True` | Adds `title` and `thumbnail` (one extra $0.003 call per link) |
| `continue_on_failure` | `False` | Log and skip failing links instead of raising |
| `max_concurrency` | `4` | Links processed at once in `aload_data` |
| `api_key` | `IMPORTLY_API_KEY` | Never serialized with the reader |

Transcripts from captions cost $0.003 per link. Media without captions raises `importly.TranscriptionProviderRequiredError` with a price quote unless you set `provider="importly"`.

Need the file or full metadata too? The same key works with the [`importly`](https://pypi.org/project/importly/) SDK.

[Importly docs](https://www.importly.io/docs?utm_source=llamaindex&utm_medium=package&utm_campaign=guerrilla-2026-11) · [Pricing](https://www.importly.io/pricing?utm_source=llamaindex&utm_medium=package&utm_campaign=guerrilla-2026-11) · support@importly.io

MIT licensed.
