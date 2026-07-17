from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CATALOG_ORDER = [
    "core.yaml",
    "hook.yaml",
    "platform.yaml",
    "skill.yaml",
    "rule.yaml",
    "command.yaml",
    "agent.yaml",
    "mcp.yaml",
    "render.yaml",
    "uri.yaml",
    "fresh.yaml",
    "install.yaml",
]


@dataclass(frozen=True)
class Vector:
    id: str
    catalog: str
    data: dict[str, Any]

    @property
    def harness(self) -> str:
        return str(self.data.get("harness", "static"))


@dataclass
class CatalogSet:
    vectors: list[Vector]
    by_id: dict[str, Vector]
    by_catalog: dict[str, list[Vector]]
    catalog_hashes: dict[str, str]


def vectors_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "vectors"


def load_catalogs() -> CatalogSet:
    root = vectors_dir()
    vectors: list[Vector] = []
    by_id: dict[str, Vector] = {}
    by_catalog: dict[str, list[Vector]] = {}
    hashes: dict[str, str] = {}

    for name in CATALOG_ORDER:
        path = root / name
        raw = path.read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        data = yaml.safe_load(raw.decode("utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{name} must contain a YAML list")
        catalog_vectors: list[Vector] = []
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ValueError(f"{name} contains a vector without a string id")
            vector = Vector(id=item["id"], catalog=name, data=item)
            if vector.id in by_id:
                raise ValueError(f"duplicate vector id {vector.id}")
            by_id[vector.id] = vector
            vectors.append(vector)
            catalog_vectors.append(vector)
        by_catalog[name] = catalog_vectors

    return CatalogSet(vectors=vectors, by_id=by_id, by_catalog=by_catalog, catalog_hashes=hashes)
