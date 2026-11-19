#!/usr/bin/env bash
# Run the unit tests of all three Python packages in one venv (needs uv).
# Live tests are skipped unless IMPORTLY_LIVE_TEST=1 and IMPORTLY_API_KEY are set
# (about $0.02 per full live run).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d .venv ] || uv venv -q ${PYTHON_VERSION:+--python "$PYTHON_VERSION"} .venv
# The loaders depend on importly from PyPI; install the local copy first so tests use it.
uv pip install -q --python .venv/bin/python -e "./importly[test]"
uv pip install -q --python .venv/bin/python -e "./langchain-importly[test]" -e "./llama-index-readers-importly[test]"
status=0
for pkg in importly langchain-importly llama-index-readers-importly; do
  echo "== $pkg"
  (cd "$pkg" && ../.venv/bin/python -m pytest -q) || status=1
done
exit $status
