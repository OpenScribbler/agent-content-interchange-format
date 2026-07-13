from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from typing import Callable

from ..report import VectorResult
from ..vectors import CatalogSet, Vector

Binding = Callable[[Vector, object, object], VectorResult]

_BINDINGS: dict[str, Binding] = {}
_LOADED = False


def binding(vector_id: str) -> Callable[[Binding], Binding]:
    def decorator(func: Binding) -> Binding:
        if vector_id in _BINDINGS:
            raise ValueError(f"duplicate binding for {vector_id}")
        _BINDINGS[vector_id] = func
        return func

    return decorator


def load_all() -> None:
    global _LOADED
    if _LOADED:
        return
    importlib.import_module(__name__ + ".core")
    importlib.import_module(__name__ + ".hook")
    importlib.import_module(__name__ + ".platform")
    importlib.import_module(__name__ + ".skill")
    importlib.import_module(__name__ + ".rule")
    importlib.import_module(__name__ + ".command")
    importlib.import_module(__name__ + ".agent")
    importlib.import_module(__name__ + ".mcp")
    importlib.import_module(__name__ + ".render")
    _LOADED = True


def get(vector_id: str) -> Binding | None:
    load_all()
    return _BINDINGS.get(vector_id)


def bound_ids() -> set[str]:
    load_all()
    return set(_BINDINGS)


def coverage_errors(catalogs: CatalogSet) -> list[str]:
    load_all()
    catalog_ids = set(catalogs.by_id)
    bound = set(_BINDINGS)
    allowed = set(UNBOUND)
    errors: list[str] = []
    for vid in sorted(catalog_ids - bound - allowed):
        errors.append(f"missing binding and not allowlisted: {vid}")
    for vid in sorted(bound & allowed):
        errors.append(f"bound id is still allowlisted: {vid}")
    for vid in sorted((bound | allowed) - catalog_ids):
        errors.append(f"binding registry mentions unknown vector id: {vid}")
    return errors


def binding_set_hash() -> str:
    root = Path(__file__).resolve().parent
    pieces: list[bytes] = []
    for path in sorted(root.glob("*.py")):
        if path.name == "__pycache__":
            continue
        pieces.append(path.name.encode("utf-8") + b"\0" + path.read_bytes())
    return hashlib.sha256(b"\n".join(pieces)).hexdigest()


UNBOUND = {
    "TV-8",  # protocol-gap: expect.installable has no PROTOCOL §4 result field
    "TV-L2-d",  # protocol-gap: frontmatter CI action/log result surface is not pinned
    "TV-L2-f",  # protocol-gap: pack-source conflict diagnostic payload params are not pinned
    "TV-L3-d",  # protocol-gap: revoked cross-reference install disposition is not exposed by resolve_reference
    "TV-AGENT-h",  # protocol-gap: render_back expectation does not name a render target
    "TV-AGENT-j",  # protocol-gap: resolve_reference has no install disposition field
    "TV-PLATFORM-a",  # protocol-gap: script selection has no PROTOCOL §4 operation/result field
    "TV-PLATFORM-b",  # protocol-gap: script selection has no PROTOCOL §4 operation/result field
    "TV-PLATFORM-h",  # protocol-gap: no-match selection has no PROTOCOL §4 operation/result field
    "TV-PLATFORM-m",  # protocol-gap: render_back expectation does not name a render target
    "TV-PLATFORM-t",  # protocol-gap: install coverage-gap disposition is not exposed by ingest/render/project
    "TV-FRESH-a",  # stage-2b
    "TV-FRESH-b",  # stage-2b
    "TV-FRESH-c",  # stage-2b
    "TV-FRESH-d",  # stage-2b
    "TV-FRESH-e",  # stage-2b
    "TV-FRESH-f",  # stage-2b
    "TV-FRESH-g",  # stage-2b
    "TV-FRESH-h",  # stage-2b
    "TV-FRESH-i",  # stage-2b
    "TV-FRESH-j",  # mock-crawl
    "TV-FRESH-k",  # stage-2b
    "TV-URI-a",  # stage-2b
    "TV-URI-b",  # stage-2b
    "TV-URI-c",  # stage-2b
    "TV-URI-d",  # stage-2b
    "TV-URI-e",  # stage-2b
    "TV-URI-f",  # stage-2b
    "TV-URI-g",  # stage-2b
    "TV-URI-h",  # stage-2b
    "TV-URI-i",  # stage-2b
    "TV-URI-j",  # stage-2b
    "TV-URI-k",  # stage-2b
    "TV-URI-l",  # mock-transport
    "TV-URI-l2",  # mock-transport
    "TV-URI-m",  # mock-transport
    "TV-URI-n",  # mock-transport
    "TV-URI-o",  # stage-2b
    "TV-URI-o2",  # stage-2b
    "TV-URI-p",  # stage-2b
    "TV-URI-q",  # stage-2b
    "TV-URI-r",  # stage-2b
    "TV-URI-s",  # stage-2b
    "TV-URI-t",  # mock-crawl
    "TV-URI-u",  # stage-2b
    "TV-URI-v",  # stage-2b
}
