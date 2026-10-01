from __future__ import annotations

import json
import os
import re
import selectors
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import RUNNER_PROTOCOL, SUPPORTED_ADAPTER_PROTOCOLS
from .scopes import SCOPE_ORDER

MAX_LINE_BYTES = 16 * 1024 * 1024
SPEC_ERROR_RE = re.compile(r"^acif\.[a-z0-9_]+(\.[a-z0-9_]+)+$")


class ProtocolError(RuntimeError):
    def __init__(self, message: str, response: "AdapterResponse | None" = None):
        super().__init__(message)
        self.response = response


@dataclass
class AdapterResponse:
    kind: str
    request_line: str
    response_line: str | None = None
    raw: Any = None
    result: dict[str, Any] | None = None
    error: str | None = None
    diagnostics: list[dict[str, Any]] | None = None
    harness_error: str | None = None

    @classmethod
    def harness(cls, request_line: str, message: str, response_line: str | None = None) -> "AdapterResponse":
        return cls(
            kind="harness-error",
            request_line=request_line,
            response_line=response_line,
            harness_error=message,
        )


def encode_request(request: dict[str, Any]) -> str:
    return json.dumps(request, ensure_ascii=False, separators=(",", ":"))


def classify_response(raw: Any, request_line: str, response_line: str | None) -> AdapterResponse:
    if not isinstance(raw, dict):
        return AdapterResponse.harness(request_line, "response is not a JSON object", response_line)

    has_ok = "ok" in raw
    has_unsupported = raw.get("unsupported") is True
    if has_unsupported:
        if has_ok or "error" in raw or "result" in raw:
            return AdapterResponse.harness(request_line, "ambiguous unsupported response", response_line)
        return AdapterResponse(kind="unsupported", request_line=request_line, response_line=response_line, raw=raw)

    if raw.get("ok") is True:
        if "error" in raw:
            return AdapterResponse.harness(request_line, "ambiguous ok response carrying error", response_line)
        result = raw.get("result")
        if not isinstance(result, dict):
            return AdapterResponse.harness(request_line, "ok response missing object result", response_line)
        return AdapterResponse(
            kind="ok",
            request_line=request_line,
            response_line=response_line,
            raw=raw,
            result=result,
        )

    if raw.get("ok") is False:
        if "result" in raw:
            return AdapterResponse.harness(request_line, "ambiguous error response carrying result", response_line)
        error = raw.get("error")
        if not isinstance(error, str) or not SPEC_ERROR_RE.match(error):
            return AdapterResponse.harness(
                request_line,
                f"non-spec error value: {error!r}",
                response_line,
            )
        diagnostics = raw.get("diagnostics", [])
        if not isinstance(diagnostics, list) or not all(isinstance(d, dict) for d in diagnostics):
            return AdapterResponse.harness(request_line, "error response diagnostics must be objects", response_line)
        return AdapterResponse(
            kind="spec-error",
            request_line=request_line,
            response_line=response_line,
            raw=raw,
            error=error,
            diagnostics=diagnostics,
        )

    return AdapterResponse.harness(request_line, "response is not one of ok/error/unsupported", response_line)


class AdapterSession:
    def __init__(self, command: str, cwd: str | Path | None = None, timeout: float = 30.0):
        self.command = command
        self.cwd = Path(cwd) if cwd is not None else None
        self.timeout = timeout
        self.process: subprocess.Popen[bytes] | None = None
        self.hello: dict[str, Any] | None = None
        self.hello_response: AdapterResponse | None = None
        self._selector: selectors.BaseSelector | None = None
        self._buffer = bytearray()

    def start(self) -> dict[str, Any]:
        argv = shlex.split(self.command)
        if not argv:
            raise ProtocolError("adapter command is empty")
        self.process = subprocess.Popen(
            argv,
            cwd=str(self.cwd) if self.cwd is not None else None,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
        )
        if self.process.stdout is None:
            raise ProtocolError("adapter stdout was not captured")
        if self.process.stdin is None:
            raise ProtocolError("adapter stdin was not captured")
        # Non-blocking stdin: an adapter that stops reading must not stall
        # the write past the per-request deadline.
        os.set_blocking(self.process.stdin.fileno(), False)
        self._selector = selectors.DefaultSelector()
        self._selector.register(self.process.stdout, selectors.EVENT_READ)
        response = self.request({"op": "hello", "runner_protocol": RUNNER_PROTOCOL})
        self.hello_response = response
        if response.kind != "ok":
            raise ProtocolError("adapter hello failed", response)
        result = response.result or {}
        adapter_protocol = result.get("adapter_protocol")
        # Exact int only: True == 1 and 2.0 == 2 both match the tuple, but
        # bindings gate protocol-2 assertions on an int and would silently
        # treat either as protocol 1.
        if type(adapter_protocol) is not int or adapter_protocol not in SUPPORTED_ADAPTER_PROTOCOLS:
            raise ProtocolError(
                f"unsupported adapter_protocol {adapter_protocol!r}; expected one of {SUPPORTED_ADAPTER_PROTOCOLS}",
                response,
            )
        scopes = result.get("scopes")
        if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
            raise ProtocolError("adapter hello scopes must be a string array", response)
        unknown = sorted(set(scopes) - set(SCOPE_ORDER))
        if unknown:
            raise ProtocolError(f"adapter hello claims unknown scope(s): {', '.join(unknown)}", response)
        self.hello = result
        return result

    def request(self, request: dict[str, Any]) -> AdapterResponse:
        request_line = encode_request(request)
        request_bytes = (request_line + "\n").encode("utf-8")
        if len(request_bytes) > MAX_LINE_BYTES:
            return AdapterResponse.harness(request_line, "request exceeds 16 MiB line limit")
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            return AdapterResponse.harness(request_line, "adapter process is not running")
        if self.process.poll() is not None:
            return AdapterResponse.harness(request_line, f"adapter process exited with {self.process.returncode}")

        deadline = time.monotonic() + self.timeout
        failure = self._write_all(request_line, request_bytes, deadline)
        if failure is not None:
            return failure

        line = self._read_line(request_line, deadline)
        if isinstance(line, AdapterResponse):
            return line
        if len(line) > MAX_LINE_BYTES:
            self._kill()
            return AdapterResponse.harness(request_line, "adapter response exceeds 16 MiB line limit")
        try:
            response_line = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            self._kill()
            return AdapterResponse.harness(request_line, f"adapter response is not UTF-8: {exc}")
        try:
            raw = json.loads(response_line)
        except json.JSONDecodeError as exc:
            self._kill()
            return AdapterResponse.harness(request_line, f"malformed JSON response: {exc}", response_line)
        return classify_response(raw, request_line, response_line)

    def _write_all(self, request_line: str, data: bytes, deadline: float) -> "AdapterResponse | None":
        """Write the request on the non-blocking stdin fd, charging every
        partial write to the per-request deadline."""
        assert self.process is not None and self.process.stdin is not None
        fd = self.process.stdin.fileno()
        view = memoryview(data)
        with selectors.DefaultSelector() as writer:
            writer.register(fd, selectors.EVENT_WRITE)
            while view:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not writer.select(remaining):
                    self._kill()
                    return AdapterResponse.harness(request_line, f"adapter request timed out after {self.timeout:g}s (adapter not reading stdin)")
                try:
                    written = os.write(fd, view)
                except BlockingIOError:
                    continue
                except OSError as exc:
                    return AdapterResponse.harness(request_line, f"adapter write failed: {exc}")
                view = view[written:]
        return None

    def _read_line(self, request_line: str, deadline: float) -> "bytes | AdapterResponse":
        """Read one response line under a single per-request deadline.

        Selector readiness only promises that some bytes are available, so a
        blocking readline() after it hangs forever on a partial line. Read the
        raw fd incrementally instead and charge every partial read to the same
        deadline."""
        assert self._selector is not None and self.process is not None and self.process.stdout is not None
        fd = self.process.stdout.fileno()
        while b"\n" not in self._buffer:
            if len(self._buffer) > MAX_LINE_BYTES:
                self._kill()
                return AdapterResponse.harness(request_line, "adapter response exceeds 16 MiB line limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._selector.select(remaining):
                self._kill()
                return AdapterResponse.harness(request_line, f"adapter request timed out after {self.timeout:g}s")
            try:
                chunk = os.read(fd, 65536)
            except OSError as exc:
                self._kill()
                return AdapterResponse.harness(request_line, f"adapter read failed: {exc}")
            if chunk == b"":
                code = self.process.poll()
                return AdapterResponse.harness(request_line, f"adapter process exited with {code}")
            self._buffer.extend(chunk)
        index = self._buffer.index(b"\n")
        line = bytes(self._buffer[:index])
        del self._buffer[: index + 1]
        return line

    def close(self) -> None:
        if self._selector is not None:
            self._selector.close()
            self._selector = None
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._kill()
        self.process = None

    def _kill(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

    def __enter__(self) -> "AdapterSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
