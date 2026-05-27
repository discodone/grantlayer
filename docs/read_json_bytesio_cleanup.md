# GL-142: Remove BytesIO Test Hack From _read_json

## What Changed

`_read_json` in `backend/src/server.py` previously contained a special-case block that detected whether `self.rfile` was an instance of `io.BytesIO` — a test-only type — and short-circuited the missing-Content-Length error in that case. This block existed solely to accommodate legacy test mocks that omitted the `Content-Length` header.

GL-142 removes this production-code hack. The function now raises `missing_content_length` (400) unconditionally when the `Content-Length` header is absent, which is the correct runtime behavior.

## What Did Not Change

- Request parsing behavior is identical for all well-formed and malformed requests.
- All error reason codes, status codes, and JSON error shapes are unchanged.
- Body-size limit (`MAX_JSON_BODY_BYTES`), empty-body rejection, non-object rejection, and malformed-JSON rejection are all unchanged.
- No endpoint or API behavior changed.
- No OpenAPI changes.
- No migration or DB schema changes.
- No auth semantics changed.
- GL-141 operator model default (`ENABLE_OPERATOR_MODEL = True`) is preserved.
- GL-140 `ThreadingHTTPServer` usage is preserved.
- GL-139 audit hash-chain write lock is preserved.

## Tests May Still Use BytesIO

Test helpers may continue to use `io.BytesIO` as a generic file-like object to back `handler.rfile`. The constraint is that production code must not detect or special-case the `BytesIO` type. Tests are isolated in a clean helper (`_make_handler`) in `test_gl142_read_json_bytesio_cleanup.py`.
