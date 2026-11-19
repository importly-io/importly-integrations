# Importly for Python

Turn any video or audio link into files, transcripts and metadata from your Python app. It works from servers and agent sandboxes, where downloads usually get blocked. Free to try, no card required: [get an API key](https://www.importly.io/login?mode=signup&utm_source=github&utm_medium=readme&utm_campaign=guerrilla-2026-11).

| Package | Install | What it is |
| --- | --- | --- |
| [`importly`](importly/) | `pip install importly` | The SDK: import (file), transcribe, metadata, basic metadata; sync and async; webhooks; typed results and errors |
| [`langchain-importly`](langchain-importly/) | `pip install langchain-importly` | `ImportlyLoader`, a LangChain document loader for video and audio links |
| [`llama-index-readers-importly`](llama-index-readers-importly/) | `pip install llama-index-readers-importly` | `ImportlyReader`, a LlamaIndex reader for video and audio links |

```python
from importly import Importly

transcript = Importly().transcribe("https://www.youtube.com/watch?v=jNQXAC9IVRw")
for chunk in transcript.chunks(60):
    print(chunk.start_timestamp, chunk.text)
```

## Development

```bash
cd python
./scripts/test.sh            # unit tests for all three packages, HTTP mocked (needs uv)
IMPORTLY_LIVE_TEST=1 IMPORTLY_API_KEY=... ./scripts/test.sh   # also hits the real API, about $0.02
```

The loaders depend on `importly` from PyPI; `test.sh` installs the local copy first. Shared test fakes are in `_testing/`.

## Releasing

Each package is published on its own by `.github/workflows/publish-python.yml`, using PyPI trusted publishing (no token).

1. Bump `version` in the package's `pyproject.toml` (and `importly/src/importly/_version.py` for the SDK), commit, push.
2. Tag and push: `git tag python-importly-v0.1.0 && git push origin python-importly-v0.1.0` (or `python-langchain-importly-v…`, `python-llama-index-readers-importly-v…`). The tag's version must match `pyproject.toml`.
3. The workflow runs the tests, builds that one package and publishes it.

Publish `importly` before the loaders, since they depend on it. You can also run the workflow by hand from the Actions tab and pick a package.
