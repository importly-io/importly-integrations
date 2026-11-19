# langchain-importly

A LangChain document loader for video and audio links. Give it links from YouTube, TikTok, X, Instagram, a podcast or 1,000+ other sites, and get transcript `Document`s with the title, duration, source URL and per-chunk timestamps.

It runs on the [Importly API](https://www.importly.io/?utm_source=langchain&utm_medium=package&utm_campaign=guerrilla-2026-11), so it keeps working once your app is deployed: from servers, serverless functions, Hugging Face Spaces and agent sandboxes, where video sites usually block downloads. Free to try, no card required.

## Install

```bash
pip install -U langchain-importly
export IMPORTLY_API_KEY=...   # https://www.importly.io/login?mode=signup&utm_source=langchain&utm_medium=package&utm_campaign=guerrilla-2026-11
```

## Use

```python
from langchain_importly import ImportlyLoader

loader = ImportlyLoader(
    [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://www.tiktok.com/@scout2015/video/6718335390845095173",
    ],
    transcript_format="chunks",   # "text" (default), "chunks" or "segments"
    chunk_size_seconds=60,
)
docs = loader.load()             # or: await loader.aload(), loader.lazy_load()

docs[0].metadata
# {'source': 'https://www.youtube.com/watch?v=jNQXAC9IVRw', 'url': '...', 'job_id': '...',
#  'language': 'en', 'transcript_source': 'platform_captions', 'duration': 19.0,
#  'title': 'Me at the zoo', 'thumbnail': '...', 'chunk_index': 0,
#  'start_seconds': 1.2, 'end_seconds': 14.367, 'start_timestamp': '00:00:01', 'end_timestamp': '00:00:14'}
```

Then split, embed and store them like any other documents. With `"chunks"`, every piece keeps its start and end time, so your app can cite or link to the moment an answer came from.

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `transcript_format` | `"text"` | One Document per link, per ~`chunk_size_seconds` window, or per caption segment |
| `chunk_size_seconds` | `120` | Window length for `"chunks"` (segments are never split) |
| `language` | captions' default | Two-letter code, e.g. `"es"` |
| `provider` | `None` | `"importly"` turns on speech-to-text for media without captions (billed per minute) |
| `max_cost_dollars` | `None` | Cap per link for speech-to-text |
| `include_metadata` | `True` | Adds `title` and `thumbnail` (one extra $0.003 call per link) |
| `continue_on_failure` | `False` | Log and skip links that fail (private, removed, no captions) instead of raising |
| `max_concurrency` | `4` | Links processed at once in `aload` / `alazy_load` |
| `api_key` | `IMPORTLY_API_KEY` | |

By default transcripts come from the media's captions ($0.003 per link). For media without captions, the loader raises `importly.TranscriptionProviderRequiredError` with a price quote; set `provider="importly"` to transcribe the audio instead.

Need the file or full metadata too? The same key works with the [`importly`](https://pypi.org/project/importly/) SDK: `Importly().import_media(url)` returns a download link.

## Links

- [Importly docs](https://www.importly.io/docs?utm_source=langchain&utm_medium=package&utm_campaign=guerrilla-2026-11)
- [Pricing](https://www.importly.io/pricing?utm_source=langchain&utm_medium=package&utm_campaign=guerrilla-2026-11)
- Support: support@importly.io

MIT licensed.
