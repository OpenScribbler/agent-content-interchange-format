from __future__ import annotations

import os
import shutil
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any


class EnvBlocked(RuntimeError):
    def __init__(self, failed: list[str]):
        super().__init__("environment probes failed: " + ", ".join(failed))
        self.failed = failed


class FixtureError(RuntimeError):
    pass


def probe_environment() -> dict[str, dict[str, Any]]:
    return {
        "byte_preserving_names": _probe_byte_preserving_names(),
        "symlink_creation": _probe_symlink_creation(),
        "case_sensitive": _probe_case_sensitive(),
        "mock_http_tls": _probe_mock_http_tls(),
    }


def _probe_byte_preserving_names() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="acif-probe-names-") as tmp:
        root = Path(tmp)
        nfc = "\u00e9"
        nfd = "e\u0301"
        try:
            (root / nfc).write_text("nfc", encoding="utf-8")
            (root / nfd).write_text("nfd", encoding="utf-8")
            entries = os.listdir(os.fsencode(root))
            ok = len(entries) == 2 and len(set(entries)) == 2
            return {"ok": ok, "detail": f"{len(entries)} distinct byte entries"}
        except OSError as exc:
            return {"ok": False, "detail": str(exc)}


def _probe_symlink_creation() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="acif-probe-symlink-") as tmp:
        root = Path(tmp)
        target = root / "target"
        link = root / "link"
        try:
            target.write_text("target", encoding="utf-8")
            os.symlink("target", link)
            return {"ok": link.is_symlink(), "detail": "created"}
        except OSError as exc:
            return {"ok": False, "detail": str(exc)}


def _probe_case_sensitive() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="acif-probe-case-") as tmp:
        root = Path(tmp)
        try:
            (root / "a.txt").write_text("lower", encoding="utf-8")
            (root / "A.txt").write_text("upper", encoding="utf-8")
            entries = set(os.listdir(root))
            ok = {"a.txt", "A.txt"} <= entries and (root / "a.txt").read_text(encoding="utf-8") == "lower"
            return {"ok": ok, "detail": f"{len(entries)} entries"}
        except OSError as exc:
            return {"ok": False, "detail": str(exc)}


def _probe_mock_http_tls() -> dict[str, Any]:
    openssl = shutil.which("openssl")
    if openssl is None:
        return {"ok": False, "detail": "openssl CLI not found; mock-transport TLS vectors are env-blocked"}
    return {"ok": True, "detail": f"openssl CLI: {openssl}"}


def required_capabilities(files: dict[str, Any]) -> set[str]:
    caps: set[str] = set()
    paths = list(files.keys())
    if any(isinstance(v, dict) and "symlink" in v for v in files.values()):
        caps.add("symlink_creation")
    if len({unicodedata.normalize("NFC", p) for p in paths}) != len(paths):
        caps.add("byte_preserving_names")
    if len({p.lower() for p in paths}) != len(paths):
        caps.add("case_sensitive")
    return caps


def assert_capabilities(env: dict[str, dict[str, Any]], caps: set[str]) -> None:
    failed = [cap for cap in sorted(caps) if not env.get(cap, {}).get("ok")]
    if failed:
        raise EnvBlocked(failed)


class FixtureContext:
    def __init__(self, env: dict[str, dict[str, Any]], keep_fixtures: bool = False, mock_http: Any = None):
        self.env = env
        self.keep_fixtures = keep_fixtures
        self.mock_http = mock_http
        self.roots: list[Path] = []
        self.observations: list[Any] = []

    def materialize(self, files: dict[str, Any]) -> str:
        assert_capabilities(self.env, required_capabilities(files))
        root = Path(tempfile.mkdtemp(prefix="acif-fixture-")).resolve()
        self.roots.append(root)
        for rel, content in files.items():
            target = _safe_path(root, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, dict) and set(content) == {"symlink"}:
                os.symlink(str(content["symlink"]), target)
            elif isinstance(content, bytes):
                target.write_bytes(content)
            elif isinstance(content, str):
                target.write_text(content, encoding="utf-8", newline="")
            else:
                raise FixtureError(f"unsupported fixture content for {rel!r}")
        return str(root)

    def cleanup(self, status: str) -> list[str]:
        paths = [str(root) for root in self.roots]
        if self.keep_fixtures or status in {"fail", "harness-error"}:
            return paths
        for root in self.roots:
            shutil.rmtree(root, ignore_errors=True)
        return []


def _safe_path(root: Path, rel: str) -> Path:
    p = PurePosixPath(rel)
    if p.is_absolute() or any(part in {"", ".."} for part in p.parts):
        raise FixtureError(f"fixture path escapes body root: {rel!r}")
    return root.joinpath(*p.parts)
