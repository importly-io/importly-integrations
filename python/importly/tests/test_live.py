"""Calls the real API. Opt in with IMPORTLY_LIVE_TEST=1 and IMPORTLY_API_KEY.

Costs about $0.006 per run (one caption transcript and one basic metadata job).
"""

import os

import pytest

from importly import Importly

URL = os.environ.get("IMPORTLY_LIVE_TEST_URL", "https://www.youtube.com/watch?v=jNQXAC9IVRw")

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("IMPORTLY_LIVE_TEST") != "1" or not os.environ.get("IMPORTLY_API_KEY"),
        reason="live test: set IMPORTLY_LIVE_TEST=1 and IMPORTLY_API_KEY",
    ),
]


def test_live_basic_metadata_and_transcript():
    with Importly() as client:
        basic = client.basic_metadata(URL, timeout=120)
        assert basic.title
        transcript = client.transcribe(URL, timeout=300)
        assert transcript.text
        assert transcript.segments
