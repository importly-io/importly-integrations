"""A scripted stand-in for the Importly API, built on httpx.MockTransport.

Queue responses per (method, path); each request pops the next one (the last
one repeats). Every request is recorded for assertions.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import httpx


def ok(data: Any) -> Tuple[int, Any]:
    return 200, {"success": True, "data": data}


def err(status: int, error: str, code: str, **extra: Any) -> Tuple[int, Any]:
    return status, {"success": False, "error": error, "code": code, **extra}


class FakeAPI:
    def __init__(self) -> None:
        self.routes: Dict[Tuple[str, str], List[Tuple[int, Any]]] = defaultdict(list)
        self.requests: List[httpx.Request] = []

    def on(self, method: str, path: str, *responses: Tuple[int, Any]) -> "FakeAPI":
        self.routes[(method, path)].extend(responses)
        return self

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        queue = self.routes.get((request.method, request.url.path))
        if not queue:
            return httpx.Response(404, json={"success": False, "error": f"no fake route {request.method} {request.url.path}", "code": "NOT_FOUND"})
        status, body = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(body, Exception):
            raise body
        return httpx.Response(status, json=body)

    def sync_client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def json_body(self, index: int) -> Any:
        return json.loads(self.requests[index].content)

    def calls(self, method: str, path: str) -> List[httpx.Request]:
        return [r for r in self.requests if r.method == method and r.url.path == path]


TRANSCRIPT_RESULT = {
    "text": "All right, so here we are, in front of the elephants\nthe cool thing about these guys is that they have really...\nreally really long trunks\nand that's cool",
    "source": "platform_captions",
    "language": "en",
    "duration": 19,
    "data": {
        "segments": [
            {"start": 1.2, "end": 3.36, "text": "All right, so here we are, in front of the elephants"},
            {"start": 5.318, "end": 7.974, "text": "the cool thing about these guys is that they have really..."},
            {"start": 7.974, "end": 12.616, "text": "really really long trunks"},
            {"start": 12.616, "end": 14.367, "text": "and that's cool"},
        ]
    },
    "costInDollars": 0.003,
}

IMPORT_RESULT = {
    "mediaUrl": "https://storage.example/imports/a8/zoo.mp3?sig=1",
    "title": "Me at the zoo",
    "duration": 19,
    "thumbnailUrl": "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg",
    "filename": "Me at the zoo.mp3",
    "fileSizeBytes": 120621,
    "downloadedBytes": 252182,
    "costInDollars": 0.01,
}

BASIC_RESULT = {"title": "Me at the zoo", "duration": 19, "thumbnail": "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg"}

URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
