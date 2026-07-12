#!/usr/bin/env python3
"""
ACIF 0.1 — hash reference implementation (Informative)

Reference implementation of:
  * body_hash for frontmatter-bearing content types ([ACIF-CORE] §7.2–§7.5):
      - single-file: canonical text form, frontmatter stripped
      - multi-file: directory manifest hash
  * body_hash for sidecar-only content types ([ACIF-CORE] §7.7,
    [ACIF-HOOK] §9, [ACIF-MCP] §8): file manifest + canonical wiring
    serialization preimage
  * metadata_hash ([ACIF-PUBLISHER] §6): canonical JSON of publisher_section
    plus a trailing LF

The multi-file directory algorithm is the MOAT v0.4.0 content-hash algorithm,
restated normatively in [ACIF-CORE] §7 (MOAT credited informatively). This
script is informative: the published vectors in ../vectors/ are the normative
authority, and where this script and a vector disagree, the vector wins.

The canonical JSON serializer here implements RFC 8785 (JCS) for the value
space the ACIF vectors exercise: objects, arrays, strings, booleans, null,
and integers within the IEEE-754 exact range. It does not implement JCS
number serialization for non-integer floats; ACIF canonical forms carry none.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
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


def directory_manifest(files: dict[str, bytes]) -> bytes:
    """[ACIF-CORE] §7.4 manifest over {relpath: bytes} (symlinks unrepresentable here)."""
    entries = []
    for rel, data in files.items():
        parts = rel.split("/")
        if any(p in VCS_DIRS for p in parts):
            continue
        if len(parts) == 1 and rel in SIDECAR_NAMES:
            continue
        nfc = unicodedata.normalize("NFC", rel)
        entries.append((nfc, file_hash(parts[-1], data)))
    if not entries:
        raise ValueError("No files found — content is unpublishable")
    entries.sort(key=lambda e: e[0].encode("utf-8"))
    return "".join(f"{h}  {p}\n" for p, h in entries).encode("utf-8")


def body_hash_multi(files: dict[str, bytes]) -> str:
    return hashlib.sha256(directory_manifest(files)).hexdigest()


def body_hash_frontmatter_type(files: dict[str, bytes], entry_file: str) -> str:
    if classify(files, entry_file) == "single-file":
        return body_hash_single(files[entry_file])
    return body_hash_multi(files)


# ── canonical JSON (RFC 8785 subset; [ACIF-CORE] §8.6) ───────────────────────

def jcs(value) -> bytes:
    """JCS for objects/arrays/strings/bools/null/ints (the ACIF value space)."""
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
        if isinstance(v, str):
            return enc_str(v)
        raise TypeError(f"unsupported JCS type: {type(v)}")

    def enc_str(s: str) -> str:
        return json.dumps(s, ensure_ascii=False, separators=(",", ":"))

    return enc(value).encode("utf-8")


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
