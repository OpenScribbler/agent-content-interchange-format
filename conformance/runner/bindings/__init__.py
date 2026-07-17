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
    importlib.import_module(__name__ + ".registry")
    importlib.import_module(__name__ + ".install")
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


UNBOUND = set()
