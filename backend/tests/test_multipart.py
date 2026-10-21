import asyncio

import pytest
from starlette.requests import Request

from app.auth.errors import AuthError
from app.ingestion.multipart import BoundedMultipartParser, upload_form
from app.ingestion.validation import MAX_BYTES


def body(content, ending=True):
    return (
        b'--test\r\nContent-Disposition: form-data; name="file"; filename="test.csv"\r\n'
        b"Content-Type: text/csv\r\n\r\n" + content + (b"\r\n--test--\r\n" if ending else b"")
    )


def parse(payload, *, disconnect=False, content_type=b"multipart/form-data; boundary=test"):
    async def run():
        offset = 0

        async def receive():
            nonlocal offset
            if offset >= len(payload) and disconnect:
                return {"type": "http.disconnect"}
            chunk = payload[offset : offset + 16384]
            offset += len(chunk)
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": offset < len(payload) or disconnect,
            }

        request = Request({"type": "http", "headers": [(b"content-type", content_type)]}, receive)
        async with upload_form(request) as form:
            file = form["file"]
            return file.size, file.file

    return asyncio.run(run())


def test_exact_file_limit_and_closed_spool():
    size, file = parse(body(b"x" * MAX_BYTES))
    assert size == MAX_BYTES and file.closed


@pytest.mark.parametrize(
    "payload,code",
    [
        (body(b"x" * (MAX_BYTES + 1)), "FILE_TOO_LARGE"),
        (body(b"x", ending=False), "INVALID_MULTIPART"),
        (b"bad boundary", "INVALID_MULTIPART"),
        (b"--test\r\nX: " + b"a" * 8193, "INVALID_MULTIPART"),
    ],
)
def test_invalid_streams(payload, code):
    with pytest.raises(AuthError) as exc:
        parse(payload)
    assert exc.value.code == code


def test_disconnect_closes_incomplete_spool(monkeypatch):
    opened = []
    original = BoundedMultipartParser.on_headers_finished

    def capture(self):
        original(self)
        opened.extend(self._files_to_close_on_error)

    monkeypatch.setattr(BoundedMultipartParser, "on_headers_finished", capture)
    with pytest.raises(AuthError, match="invalid or incomplete"):
        parse(body(b"x" * 1024, ending=False), disconnect=True)
    assert opened and all(file.closed for file in opened)


def test_content_type_required():
    with pytest.raises(AuthError) as exc:
        parse(b"{}", content_type=b"application/json")
    assert exc.value.status == 415
