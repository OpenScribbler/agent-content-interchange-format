#!/usr/bin/env python3
"""
ACIF 0.1 — frontmatter-to-publisher_section reference implementation (Informative)

Reference implementation of:
  * the frontmatter parse ([ACIF-CORE] §2): YAML 1.2 core schema, with the
    malformed conditions (top level not a map; a duplicate or non-string key;
    an anchor, alias, or explicit tag; a raw U+0085, U+2028, or U+2029;
    nesting deeper than 64; a key or string that is not Unicode scalar values
    or holds a noncharacter; a float that is not finite; an int beyond
    ±(2^53−1))
  * the frontmatter-to-publisher_section construction ([ACIF-PUBLISHER] §5.6):
    no-declaration cases, null-as-absent, forbidden fields, the kind check,
    placement, and envelope validation, in that precedence order

PyYAML implements YAML 1.1 (`yes` is a boolean, `0777` is octal 511,
`2024-01-01` is a date), so this module builds a loader whose implicit
resolvers are exactly the YAML 1.2 core schema's. Anchors, aliases, tags, and
depth are checked on the event stream before any node is composed, so a
hostile block never expands. Raw U+0085, U+2028, and U+2029 are rejected
before parsing, which also keeps PyYAML's 1.1 scanner from reading them as
line breaks. The scanner is patched to accept a tab as in-line separation
(`a:<TAB>b`, `a: b<TAB># c`) and inside a plain scalar (`a: b<TAB>c`).

Known gap against YAML 1.2: a tab that starts a line, including a
continuation line of a multi-line plain or flow scalar, is rejected where a
1.2 parser can accept it.

Step 7 checks `id` and `version`, in that order. It omits the SPDX
license-list check behind `acif.envelope.license_spdx_invalid`, as the
reference adapter does for sidecars (TV-11 case_4 is a baseline fail there).

The published vectors are the normative authority; where this module and a
vector disagree, the vector wins.
"""
from __future__ import annotations

import math
import re

import yaml

from acif_hash import canonical_text

KINDS = ("hook", "skill", "rule", "command", "agent", "mcp_config", "pack")
FRONTMATTER_KINDS = frozenset({"skill", "rule", "command", "agent"})
ENVELOPE_KEYS = frozenset({"kind", "id", "display_name", "version", "description", "pack_id"})
FORBIDDEN_FIELDS = frozenset({"effective_version", "derived_version", "pack_inherited_version", "resolved_version"})
MAX_SAFE_INTEGER = 2**53 - 1
MAX_DEPTH = 64
RAW_LINE_SEPARATORS = ("\u0085", "\u2028", "\u2029")

UUID_V4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class FrontmatterReject(Exception):
    """A rejected frontmatter declaration. `verdict` is True for the
    [ACIF-CORE] §8.7 `reject (verdict)` identifiers, which travel as a
    `{conformant: false}` verdict; the others travel as an ingest error."""

    def __init__(self, error: str, *, verdict: bool = False, params: dict | None = None):
        super().__init__(error)
        self.error = error
        self.verdict = verdict
        self.params = params or {}


# ── YAML 1.2 core-schema loader ─────────────────────────────────────────────

_INT_DEC = re.compile(r"^[-+]?[0-9]+$")
_INT_OCT = re.compile(r"^0o[0-7]+$")
_INT_HEX = re.compile(r"^0x[0-9a-fA-F]+$")
_FLOAT = re.compile(r"^[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?$")
_INF = re.compile(r"^[-+]?\.(inf|Inf|INF)$")
_NAN = re.compile(r"^\.(nan|NaN|NAN)$")


class _CoreResolver(yaml.resolver.Resolver):
    yaml_implicit_resolvers: dict = {}


_CoreResolver.add_implicit_resolver(
    "tag:yaml.org,2002:null", re.compile(r"^(?:~|null|Null|NULL|)$"), ["~", "n", "N", ""]
)
_CoreResolver.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)
_CoreResolver.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"),
    list("-+0123456789"),
)
_CoreResolver.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"),
    list("-+.0123456789"),
)


class _CoreConstructor(yaml.constructor.BaseConstructor):
    yaml_constructors: dict = {}

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise yaml.constructor.ConstructorError(None, None, "expected a mapping", node.start_mark)
        mapping: dict = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise FrontmatterReject("acif.frontmatter.malformed", params={"reason": "non-string key"})
            if key in mapping:
                raise FrontmatterReject("acif.frontmatter.malformed", params={"reason": f"duplicate key {key!r}"})
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _construct_null(loader, node):
    loader.construct_scalar(node)
    return None


def _construct_bool(loader, node):
    return loader.construct_scalar(node).lower() == "true"


def _construct_int(loader, node):
    value = loader.construct_scalar(node)
    if _INT_DEC.fullmatch(value):
        try:
            return int(value, 10)
        except ValueError:  # beyond Python's int-from-text digit limit
            raise _malformed("integer text too long") from None
    if _INT_OCT.fullmatch(value):
        return int(value[2:], 8)
    if _INT_HEX.fullmatch(value):
        return int(value[2:], 16)
    raise FrontmatterReject("acif.frontmatter.malformed", params={"reason": f"not a core-schema int {value!r}"})


def _construct_float(loader, node):
    value = loader.construct_scalar(node)
    if _INF.fullmatch(value):
        return -math.inf if value.startswith("-") else math.inf
    if _NAN.fullmatch(value):
        return math.nan
    if _FLOAT.fullmatch(value):
        return float(value)
    raise FrontmatterReject("acif.frontmatter.malformed", params={"reason": f"not a core-schema float {value!r}"})


def _construct_str(loader, node):
    return loader.construct_scalar(node)


def _construct_seq(loader, node):
    return loader.construct_sequence(node, deep=True)


def _construct_map(loader, node):
    return loader.construct_mapping(node, deep=True)


def _construct_unknown(loader, node):
    raise FrontmatterReject("acif.frontmatter.malformed", params={"reason": f"tag {node.tag} outside the core schema"})


for _tag, _fn in (
    ("tag:yaml.org,2002:null", _construct_null),
    ("tag:yaml.org,2002:bool", _construct_bool),
    ("tag:yaml.org,2002:int", _construct_int),
    ("tag:yaml.org,2002:float", _construct_float),
    ("tag:yaml.org,2002:str", _construct_str),
    ("tag:yaml.org,2002:seq", _construct_seq),
    ("tag:yaml.org,2002:map", _construct_map),
    (None, _construct_unknown),
):
    _CoreConstructor.add_constructor(_tag, _fn)


class _TabScanner(yaml.scanner.Scanner):
    """PyYAML's 1.1 scanner with YAML 1.2 tab handling where it is contained:
    a tab after content on the same line separates tokens, and a tab between
    two words is part of a plain scalar. A tab that starts a line is still
    refused (YAML forbids tabs in indentation)."""

    def _after_content(self) -> bool:
        return self.buffer[self.pointer - self.column:self.pointer].strip(" \t") != ""

    def scan_to_next_token(self):
        if self.index == 0 and self.peek() == "\uFEFF":
            self.forward()
        found = False
        while not found:
            while self.peek() == " " or (self.peek() == "\t" and self._after_content()):
                self.forward()
            if self.peek() == "#":
                while self.peek() not in "\0\r\n\x85\u2028\u2029":
                    self.forward()
            if self.scan_line_break():
                if not self.flow_level:
                    self.allow_simple_key = True
            else:
                found = True

    def scan_plain_spaces(self, indent, start_mark):
        length = 0
        while self.peek(length) in " \t":
            length += 1
        if "\t" not in self.prefix(length):
            return super().scan_plain_spaces(indent, start_mark)
        whitespaces = self.prefix(length)
        self.forward(length)
        if self.peek() in "\r\n\x85\u2028\u2029":
            return super().scan_plain_spaces(indent, start_mark)
        return [whitespaces]


class CoreSchemaLoader(
    yaml.reader.Reader,
    _TabScanner,
    yaml.parser.Parser,
    yaml.composer.Composer,
    _CoreConstructor,
    _CoreResolver,
):
    def __init__(self, stream):
        yaml.reader.Reader.__init__(self, stream)
        _TabScanner.__init__(self)
        yaml.parser.Parser.__init__(self)
        yaml.composer.Composer.__init__(self)
        _CoreConstructor.__init__(self)
        _CoreResolver.__init__(self)


def _malformed(reason: str) -> FrontmatterReject:
    return FrontmatterReject("acif.frontmatter.malformed", params={"reason": reason})


def _check_events(text: str) -> None:
    """[ACIF-CORE] §2 on the event stream, before composing: no anchor, alias,
    or explicit tag, and no nesting deeper than MAX_DEPTH (the top-level map
    is level 1)."""
    depth = 0
    for event in yaml.parse(text, Loader=CoreSchemaLoader):
        if isinstance(event, yaml.AliasEvent):
            raise _malformed("alias")
        if getattr(event, "anchor", None) is not None:
            raise _malformed("anchor")
        if getattr(event, "tag", None) is not None:
            raise _malformed(f"explicit tag {event.tag}")
        if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
            depth += 1
            if depth > MAX_DEPTH:
                raise _malformed(f"nesting deeper than {MAX_DEPTH}")
        elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
            depth -= 1


def _check_string(value: str) -> None:
    for ch in value:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            raise _malformed(f"surrogate U+{cp:04X}")
        if 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFE) == 0xFFFE:
            raise _malformed(f"noncharacter U+{cp:04X}")


def _check_values(value) -> None:
    """Every key and string is Unicode scalar values with no noncharacters; a
    float is finite; an int (only an int-resolved scalar) is within
    ±(2^53−1)."""
    if isinstance(value, dict):
        for key, child in value.items():
            _check_string(key)
            _check_values(child)
    elif isinstance(value, list):
        for child in value:
            _check_values(child)
    elif isinstance(value, str):
        _check_string(value)
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise _malformed(f"integer {value} beyond ±(2^53−1)")
    elif isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise _malformed("float not finite")


def load_core(text: str):
    """Parse one YAML document under the 1.2 core schema; malformed → reject.
    Every [ACIF-CORE] §2 condition is checked here, in [ACIF-PUBLISHER] §5.6
    step 1, ahead of every later step."""
    for ch in RAW_LINE_SEPARATORS:
        if ch in text:
            raise _malformed(f"raw U+{ord(ch):04X}")
    try:
        _check_events(text)
        loader = CoreSchemaLoader(text)
        try:
            value = loader.get_single_data()
        finally:
            loader.dispose()
    except yaml.YAMLError as exc:
        raise _malformed(str(exc).splitlines()[0]) from exc
    _check_values(value)
    return value


# ── frontmatter block ([ACIF-CORE] §7.3 delimiters) ─────────────────────────

def frontmatter_block(data: bytes) -> str | None:
    """The text between the delimiter lines, or None when the file carries no
    frontmatter block. The closing `---` line ends in LF or end of input, and
    may immediately follow the opening line."""
    text = canonical_text(data).decode("utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end != -1:
        return text[4:end + 1] if end >= 4 else ""
    if text.endswith("\n---"):
        return text[4:len(text) - 3] if len(text) > 7 else ""
    return None


# ── publisher_section construction ([ACIF-PUBLISHER] §5.6) ──────────────────

def publisher_section_from_frontmatter(data: bytes, kind: str) -> dict | None:
    """Apply [ACIF-PUBLISHER] §5.6 to an entry file's bytes for an item the
    ingestion context assigns `kind`. Returns the publisher_section, or None
    when the file declares nothing. Raises FrontmatterReject; the first
    failing step wins."""
    block = frontmatter_block(data)
    if block is None:
        return None
    return publisher_section_from_mapping(load_core(block), kind)


def publisher_section_from_mapping(parsed, kind: str) -> dict | None:
    # 1. Parse: the top level is a map (or declares nothing).
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise FrontmatterReject("acif.frontmatter.malformed", params={"reason": "top level is not a map"})
    # 2–3. No declaration; a null-valued top-level key is absent.
    declared = {key: value for key, value in parsed.items() if value is not None}
    if not declared:
        return None
    # 4. Forbidden fields.
    for key in declared:
        if key in FORBIDDEN_FIELDS:
            raise FrontmatterReject("acif.envelope.forbidden_field", verdict=True, params={"field": key})
    # 5. kind check.
    if "kind" in declared:
        declared_kind = declared["kind"]
        if declared_kind not in KINDS:
            raise FrontmatterReject("acif.envelope.kind_invalid", verdict=True)
        if declared_kind not in FRONTMATTER_KINDS or declared_kind != kind:
            raise FrontmatterReject(
                "acif.publisher.frontmatter_kind_mismatch",
                params={"declared": declared_kind, "assigned": kind},
            )
    # 6. Placement by top-level key name.
    section: dict = {}
    extension: dict = {}
    for key, value in declared.items():
        if key in ENVELOPE_KEYS or (key == "license" and isinstance(value, dict)):
            section[key] = value
        else:
            extension[key] = value
    if extension:
        section[kind] = extension
    # 7. Envelope validation of the placed values.
    if "id" in section and not (isinstance(section["id"], str) and UUID_V4.fullmatch(section["id"])):
        raise FrontmatterReject("acif.envelope.id_invalid", verdict=True)
    if "version" in section and not (isinstance(section["version"], str) and SEMVER.fullmatch(section["version"])):
        raise FrontmatterReject("acif.envelope.version_invalid", verdict=True)
    return section
