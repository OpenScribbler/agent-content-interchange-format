#!/usr/bin/env python3
"""
ACIF 0.1 — hash reference implementation (Informative)

Reference implementation of:
  * body_hash for frontmatter-bearing content types ([ACIF-CORE] §7.2–§7.5):
      - single-file: canonical text form, frontmatter stripped
      - multi-file: directory manifest hash, the entry file's frontmatter
        stripped in its per-file hash ([ACIF-CORE] §7.3)
  * body_hash for sidecar-only content types ([ACIF-CORE] §7.7,
    [ACIF-HOOK] §9, [ACIF-MCP] §8): file manifest + canonical wiring
    serialization preimage
  * metadata_hash ([ACIF-PUBLISHER] §6): canonical JSON of publisher_section
    plus a trailing LF

The multi-file directory algorithm is the MOAT v0.4.0 content-hash algorithm,
restated normatively in [ACIF-CORE] §7 (MOAT credited informatively). This
script is informative: the published vectors in ../vectors/ are the normative
authority, and where this script and a vector disagree, the vector wins.

The canonical JSON serializer here implements RFC 8785 (JCS) for the I-JSON
value space: objects, arrays, strings, booleans, null, integers within the
IEEE-754 exact range, and finite floats serialized with the ECMAScript
Number-to-string rule RFC 8785 §3.2.2.3 adopts (frontmatter values parsed
under the YAML 1.2 core schema can be floats; [ACIF-PUBLISHER] §5.6).
"""
from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from decimal import Decimal
from pathlib import Path

TEXT_EXTENSIONS = frozenset({
    ".md", ".txt", ".rst",
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf",
    ".html", ".htm", ".xml", ".svg", ".css", ".scss", ".less",
    ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".py", ".rb", ".lua", ".rs", ".go",
    ".sh", ".bash", ".zsh", ".fish",
    ".csv", ".tsv", ".sql",
    ".lock", ".sum", ".mod",
})

UTF8_BOM = b"\xef\xbb\xbf"
NUL_SCAN = 8192
VCS_DIRS = frozenset({".git", ".svn", ".hg", ".bzr", "_darcs", ".fossil"})

# Registry-generated sidecar filename, excluded at the body root only
# ([ACIF-CORE] §7.5). The name is registry-conventional; vectors use this one.
SIDECAR_NAMES = frozenset({"acif-sidecar.yaml"})


class BodyReject(ValueError):
    """A [ACIF-CORE] §7.4 reject, carrying its §8.7 identifier."""

    def __init__(self, error: str, path: str):
        super().__init__(f"{error}: {path!r}")
        self.error = error
        self.path = path


def _has_control_char(rel: str) -> bool:
    return any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in rel)


def _is_utf8(rel: str) -> bool:
    """A name read from the filesystem decodes with surrogateescape, so a byte
    that is not UTF-8 arrives as a lone surrogate; a surrogate in a name taken
    from JSON or YAML is not a Unicode scalar value either. Neither encodes as
    UTF-8."""
    return not any(0xD800 <= ord(ch) <= 0xDFFF for ch in rel)


def check_raw_paths(paths) -> None:
    """[ACIF-CORE] §7.4 step 3, over the raw relative paths before NFC. The
    UTF-8 scan covers every path before the control-character scan starts,
    and both finish before any collision check: a path that is not valid
    UTF-8 rejects with acif.body.path_not_utf8, then a path containing
    U+0000–U+001F or U+007F in any component rejects with
    acif.body.path_control_char. U+0080–U+009F are not control characters for
    this rule."""
    paths = list(paths)
    for rel in paths:
        if not _is_utf8(rel):
            raise BodyReject("acif.body.path_not_utf8", rel)
    for rel in paths:
        if _has_control_char(rel):
            raise BodyReject("acif.body.path_control_char", rel)


# ── canonical text form ([ACIF-CORE] §7.3) ──────────────────────────────────

def canonical_text(data: bytes) -> bytes:
    """BOM strip + single-pass CRLF/CR → LF normalization."""
    if data.startswith(UTF8_BOM):
        data = data[3:]
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0x0D:                       # CR
            out.append(0x0A)
            if i + 1 < n and data[i + 1] == 0x0A:
                i += 2                      # CRLF
            else:
                i += 1                      # lone CR
        else:
            out.append(b)
            i += 1
    return bytes(out)


def final_extension(name: str) -> str:
    if name.startswith(".") and name.count(".") == 1:
        return ""
    return Path(name).suffix.lower()


def is_text(name: str, data: bytes) -> bool:
    if final_extension(name) not in TEXT_EXTENSIONS:
        return False
    return b"\x00" not in data[:NUL_SCAN]


def file_hash(name: str, data: bytes) -> str:
    if is_text(name, data):
        return hashlib.sha256(canonical_text(data)).hexdigest()
    return hashlib.sha256(data).hexdigest()


# ── frontmatter strip ([ACIF-CORE] §7.3, single-file bodies) ─────────────────

def strip_frontmatter(data: bytes) -> bytes:
    """Remove a leading YAML frontmatter block delimited by '---' lines.
    The closing delimiter line may be terminated by LF or by end of input
    ([ACIF-CORE] §7.3)."""
    text = canonical_text(data)
    if not text.startswith(b"---\n"):
        return text
    end = text.find(b"\n---\n", 3)
    if end != -1:
        return text[end + len(b"\n---\n"):]
    if text.endswith(b"\n---"):
        return b""
    return text


# ── body classification ([ACIF-CORE] §7.2) ───────────────────────────────────

def _excluded_at_root(name: str) -> bool:
    upper = name.upper()
    return upper.startswith("LICENSE") or upper.startswith("README") \
        or name in SIDECAR_NAMES


def classify(files: dict[str, bytes], entry_file: str) -> str:
    """Return 'single-file' or 'multi-file' for a body given as {relpath: bytes}."""
    for rel in files:
        parts = rel.split("/")
        if any(p in VCS_DIRS for p in parts):
            continue
        if len(parts) == 1 and (_excluded_at_root(parts[0]) or rel == entry_file):
            continue
        return "multi-file"
    return "single-file"


# ── body_hash, frontmatter-bearing types ─────────────────────────────────────

def body_hash_single(entry_bytes: bytes) -> str:
    """Single-file body: canonical text, frontmatter stripped."""
    return hashlib.sha256(strip_frontmatter(entry_bytes)).hexdigest()


def directory_manifest(files: dict[str, bytes], entry_file: str | None = None) -> bytes:
    """[ACIF-CORE] §7.4 manifest over {relpath: bytes} (symlinks unrepresentable
    here). The entry file's per-file hash input is its frontmatter-stripped
    canonical text form ([ACIF-CORE] §7.3)."""
    enumerated = {rel: data for rel, data in files.items() if not any(p in VCS_DIRS for p in rel.split("/"))}
    check_raw_paths(enumerated)
    entries = []
    for rel, data in enumerated.items():
        parts = rel.split("/")
        if len(parts) == 1 and rel in SIDECAR_NAMES:
            continue
        nfc = unicodedata.normalize("NFC", rel)
        if rel == entry_file:
            h = hashlib.sha256(strip_frontmatter(data)).hexdigest()
        else:
            h = file_hash(parts[-1], data)
        entries.append((nfc, h))
    if not entries:
        raise ValueError("No files found — content is unpublishable")
    entries.sort(key=lambda e: e[0].encode("utf-8"))
    return "".join(f"{h}  {p}\n" for p, h in entries).encode("utf-8")


def body_hash_multi(files: dict[str, bytes], entry_file: str | None = None) -> str:
    return hashlib.sha256(directory_manifest(files, entry_file)).hexdigest()


def body_hash_frontmatter_type(files: dict[str, bytes], entry_file: str) -> str:
    if classify(files, entry_file) == "single-file":
        return body_hash_single(files[entry_file])
    return body_hash_multi(files, entry_file)


# ── canonical JSON (RFC 8785 subset; [ACIF-CORE] §8.6) ───────────────────────

def jcs(value) -> bytes:
    """JCS over the I-JSON value space (RFC 8785)."""
    def enc(v):
        if isinstance(v, dict):
            items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-16-be"))
            return "{" + ",".join(f"{enc_str(k)}:{enc(val)}" for k, val in items) + "}"
        if isinstance(v, list):
            return "[" + ",".join(enc(x) for x in v) + "]"
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return es6_number(v)
        if isinstance(v, str):
            return enc_str(v)
        raise TypeError(f"unsupported JCS type: {type(v)}")

    def enc_str(s: str) -> str:
        return json.dumps(s, ensure_ascii=False, separators=(",", ":"))

    return enc(value).encode("utf-8")


def es6_number(x: float) -> str:
    """ECMAScript Number.prototype.toString for a finite double, the number
    serialization RFC 8785 §3.2.2.3 pins: shortest round-trip digits, no
    trailing ".0", exponent form outside [1e-6, 1e21)."""
    if math.isnan(x) or math.isinf(x):
        raise TypeError("JCS cannot serialize NaN or Infinity")
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    _, digit_tuple, exp = Decimal(repr(abs(x))).as_tuple()
    digits = "".join(str(d) for d in digit_tuple).lstrip("0")
    stripped = digits.rstrip("0")
    exp += len(digits) - len(stripped)
    s, k = stripped, len(stripped)
    n = k + exp  # value = 0.s × 10^n
    if k <= n <= 21:
        out = s + "0" * (n - k)
    elif 0 < n <= 21:
        out = s[:n] + "." + s[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + s
    else:
        e = n - 1
        mantissa = s[0] + ("." + s[1:] if k > 1 else "")
        out = f"{mantissa}e{'+' if e > 0 else '-'}{abs(e)}"
    return sign + out


# ── sidecar-only preimage ([ACIF-CORE] §7.7; [ACIF-HOOK] §9; [ACIF-MCP] §8) ──

def sidecar_only_body_hash(wiring: dict, referenced_files: dict[str, bytes]) -> str:
    """
    preimage = UTF8(DH) || 0x0A || W || 0x0A
      DH = "sha256:" + hex(SHA-256(manifest bytes))    (empty manifest → empty bytes)
      W  = JCS(canonical extension block)
    Callers pass the extension block ALREADY in canonical form: defaults
    materialized, vocabularies translated, canonical array ordering applied
    ([ACIF-HOOK] §9.3, [ACIF-MCP] §8.3), inline content LF-normalized.
    """
    if referenced_files:
        check_raw_paths(referenced_files)
        entries = []
        for rel, data in referenced_files.items():
            nfc = unicodedata.normalize("NFC", rel)
            entries.append((nfc, file_hash(rel.split("/")[-1], data)))
        entries.sort(key=lambda e: e[0].encode("utf-8"))
        manifest = "".join(f"{h}  {p}\n" for p, h in entries).encode("utf-8")
    else:
        manifest = b""
    dh = "sha256:" + hashlib.sha256(manifest).hexdigest()
    preimage = dh.encode("utf-8") + b"\n" + jcs(wiring) + b"\n"
    return hashlib.sha256(preimage).hexdigest()


# ── metadata_hash ([ACIF-PUBLISHER] §6) ──────────────────────────────────────

def metadata_hash(publisher_section: dict) -> str:
    return hashlib.sha256(jcs(publisher_section) + b"\n").hexdigest()
