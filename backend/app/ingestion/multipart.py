"""Streaming multipart bounds on top of the pinned Starlette parser."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import anyio
from fastapi import Request
from starlette.datastructures import FormData
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import ClientDisconnect

from app.auth.errors import AuthError
from app.ingestion.validation import MAX_BYTES


class BoundedMultipartParser(MultiPartParser):
    file_bytes = 0
    header_bytes = 0
    complete = False

    def on_part_begin(self) -> None:
        self.header_bytes = 0
        super().on_part_begin()

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self.header_bytes += end - start
        if self.header_bytes > 8192:
            raise MultiPartException("Headers too large")
        super().on_header_field(data, start, end)

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self.header_bytes += end - start
        if self.header_bytes > 8192:
            raise MultiPartException("Headers too large")
        super().on_header_value(data, start, end)

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            self.file_bytes += end - start
            if self.file_bytes > MAX_BYTES:
                raise AuthError(413, "FILE_TOO_LARGE", "CSV must not exceed 10 MiB.")
        super().on_part_data(data, start, end)

    def on_end(self) -> None:
        self.complete = True


@asynccontextmanager
async def upload_form(request: Request) -> AsyncIterator[FormData]:
    content_type = request.headers.get("content-type", "")
    if content_type.split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise AuthError(415, "MULTIPART_REQUIRED", "Send one CSV as multipart form data.")
    if len(content_type) > 1024:
        raise AuthError(400, "INVALID_MULTIPART", "Multipart headers are invalid.")

    async def bounded_stream() -> AsyncGenerator[bytes, None]:
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_BYTES + 16 * 1024:
                raise AuthError(413, "FILE_TOO_LARGE", "Upload exceeds the request limit.")
            for offset in range(0, len(chunk), 64 * 1024):
                yield chunk[offset : offset + 64 * 1024]

    parser = BoundedMultipartParser(
        request.headers, bounded_stream(), max_files=1, max_fields=3, max_part_size=512
    )
    try:
        with anyio.fail_after(60):
            form = await parser.parse()
        if not parser.complete:
            raise MultiPartException("Incomplete body")
        yield form
    except (MultiPartException, ClientDisconnect):
        raise AuthError(
            400, "INVALID_MULTIPART", "Multipart upload is invalid or incomplete."
        ) from None
    except TimeoutError:
        raise AuthError(408, "UPLOAD_TIMEOUT", "Upload timed out. Try again.") from None
    finally:
        # Also close incomplete parts omitted from FormData, including on cancellation.
        for file in parser._files_to_close_on_error:
            file.close()
