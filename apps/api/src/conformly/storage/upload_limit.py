"""Bound multipart bodies before the framework parses or spools them."""

from tempfile import SpooledTemporaryFile

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class UploadLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "").rstrip("/")
        if not (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and path.startswith("/v1/tenants/")
            and path.endswith("/files")
        ):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length is not None:
            try:
                oversized = int(length) > self.max_body_bytes or int(length) < 0
            except ValueError:
                oversized = True
            if oversized:
                await JSONResponse({"detail": "Upload body exceeds limit"}, 413)(
                    scope, receive, send
                )
                return
        # A disk-backed, bounded spool also handles chunked bodies with no Content-Length.
        with SpooledTemporaryFile(max_size=1024 * 1024) as body:
            total = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                total += len(chunk)
                if total > self.max_body_bytes:
                    await JSONResponse({"detail": "Upload body exceeds limit"}, 413)(
                        scope, receive, send
                    )
                    return
                body.write(chunk)
                if not message.get("more_body", False):
                    break
            body.seek(0)
            delivered = False

            async def replay() -> Message:
                nonlocal delivered
                if delivered:
                    return await receive()
                chunk = body.read(64 * 1024)
                more = body.tell() < total
                delivered = not more
                return {"type": "http.request", "body": chunk, "more_body": more}

            await self.app(scope, replay, send)
