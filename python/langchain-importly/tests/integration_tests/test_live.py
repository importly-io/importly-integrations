"""Calls the real API. Opt in with IMPORTLY_LIVE_TEST=1 and IMPORTLY_API_KEY (about $0.006 a run)."""

import os

import pytest

from langchain_importly import ImportlyLoader

URL = os.environ.get("IMPORTLY_LIVE_TEST_URL", "https://www.youtube.com/watch?v=jNQXAC9IVRw")

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("IMPORTLY_LIVE_TEST") != "1" or not os.environ.get("IMPORTLY_API_KEY"),
        reason="live test: set IMPORTLY_LIVE_TEST=1 and IMPORTLY_API_KEY",
    ),
]


def test_live_chunks():
    docs = ImportlyLoader(URL, transcript_format="chunks", chunk_size_seconds=30, timeout=300).load()
    assert docs
    assert docs[0].metadata["source"] == URL
    assert docs[0].metadata.get("title")
    assert "start_seconds" in docs[0].metadata
