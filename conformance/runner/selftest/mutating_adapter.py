from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["field", "distinct-perturb", "memoize"], default="field")
    parser.add_argument("child", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    argv = args.child
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("mutating_adapter requires a child command", file=sys.stderr)
        return 2
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, text=True, encoding="utf-8")
    assert child.stdin is not None and child.stdout is not None
    response_counter = 0
    memoized_ok_by_op: dict[str, dict[str, Any]] = {}
    for line in sys.stdin:
        request = json.loads(line)
        child.stdin.write(line)
        child.stdin.flush()
        response_line = child.stdout.readline()
        if not response_line:
            print(json.dumps({"ok": False, "error": "adapter: child exited"}), flush=True)
            continue
        if request.get("op") == "hello":
            print(response_line.rstrip("\n"), flush=True)
            continue
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError:
            print(response_line.rstrip("\n"), flush=True)
            continue
        response_counter += 1
        if args.mode == "memoize":
            op = str(request.get("op"))
            if op in memoized_ok_by_op:
                response = json.loads(json.dumps(memoized_ok_by_op[op]))
            elif response.get("ok") is True:
                memoized_ok_by_op[op] = json.loads(json.dumps(response))
        else:
            response = mutate_response(response, mode=args.mode, counter=response_counter)
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
    child.terminate()
    return 0


def mutate_response(response: dict[str, Any], *, mode: str = "field", counter: int = 0) -> dict[str, Any]:
    out = json.loads(json.dumps(response))
    if mode == "distinct-perturb" and out.get("ok") is True:
        return {"ok": False, "error": "acif.sabotage.mutated", "diagnostics": []}
    if out.get("ok") is True and isinstance(out.get("result"), dict):
        out["result"] = mutate_value(out["result"], mode=mode, counter=counter)
    if out.get("ok") is False and isinstance(out.get("error"), str) and out["error"].startswith("acif."):
        out["error"] = out["error"] + ".mutated"
    if isinstance(out.get("diagnostics"), list):
        out["diagnostics"] = mutate_value(out["diagnostics"], mode=mode, counter=counter)
    return out


def mutate_value(value: Any, key: str | None = None, *, mode: str = "field", counter: int = 0) -> Any:
    if isinstance(value, dict):
        return {k: mutate_value(v, k, mode=mode, counter=counter) for k, v in value.items()}
    if isinstance(value, list):
        return [mutate_value(v, key, mode=mode, counter=counter) for v in value]
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        if key and "hash" in key and HEX_RE.match(value):
            return flip_hex(value, counter if mode == "distinct-perturb" else 0)
        if key in {"id", "error"} and value.startswith("acif."):
            return value + ".mutated"
        suffix = f".mutated{counter}" if mode == "distinct-perturb" else ".mutated"
        return value + suffix
    return value


def flip_hex(value: str, offset: int = 0) -> str:
    idx = offset % len(value)
    replacement = "1" if value[idx] != "1" else "0"
    return value[:idx] + replacement + value[idx + 1 :]


if __name__ == "__main__":
    raise SystemExit(main())
