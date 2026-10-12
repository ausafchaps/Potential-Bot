import re

from starlette.responses import JSONResponse

from app.core.config import settings


class UploadBodyLimitMiddleware:
    """Bound multipart bodies before parsing/spooling, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        upload_path = re.fullmatch(r"/courses/[^/]+/documents/(text|pdf)/?", scope.get("path", ""))
        if (scope["type"] != "http" or scope.get("method") != "POST"
                or not upload_path):
            return await self.app(scope, receive, send)
        # Permit multipart headers in addition to the file itself. The file gets
        # its own exact byte check after the authenticated upload dependencies.
        limit = settings.upload_max_bytes + 64 * 1024
        response = JSONResponse(status_code=413, content={
            "detail": "Upload request is too large. Choose a smaller file or split your notes."},
            headers={"Cache-Control": "no-store"})
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > limit:
                        return await response(scope, receive, send)
                except ValueError:
                    pass
        buffered_body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            if len(buffered_body) + len(body) > limit:
                return await response(scope, receive, send)
            buffered_body.extend(body)
            if not message.get("more_body", False):
                break
        complete_body = bytes(buffered_body)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": complete_body, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
