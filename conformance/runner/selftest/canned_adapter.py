from __future__ import annotations

import json
import sys
from typing import Any


def emit(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, separators=(",", ":")), flush=True)


def main() -> int:
    for line in sys.stdin:
        request = json.loads(line)
        if request.get("op") == "hello":
            emit(
                {
                    "ok": True,
                    "result": {
                        "implementation": "canned",
                        "version": "0",
                        "adapter_protocol": 2,
                        "scopes": ["core", "hook"],
                    },
                }
            )
        elif request.get("op") == "ingest":
            emit({"ok": True, "result": {"conformant": True, "body_hash": "0" * 64}})
        else:
            emit({"unsupported": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
