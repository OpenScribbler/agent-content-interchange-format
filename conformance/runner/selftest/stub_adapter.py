"""Misbehaving adapters for the runner's regression selftests.

--mode empty           claims core and answers every request {"ok":true,"result":{}}
--mode partial         answers hello, then writes half a response line and stalls
--mode no-read         answers hello, then stops reading stdin
--mode bool-protocol   answers hello with adapter_protocol true
--mode float-protocol  answers hello with adapter_protocol 2.0
--mode unknown-scope   answers hello claiming a scope the runner does not know
--mode partial-fields  claims core and hook; answers every request with the
                       verdict and classification fields but no hash, identity
                       or provenance field
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def reply(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=["empty", "partial", "no-read", "bool-protocol", "float-protocol", "unknown-scope", "partial-fields"],
    )
    args = parser.parse_args()
    hello = {"implementation": "stub", "version": "0", "adapter_protocol": 2, "scopes": ["core"]}
    if args.mode == "bool-protocol":
        hello["adapter_protocol"] = True
    if args.mode == "float-protocol":
        hello["adapter_protocol"] = 2.0
    if args.mode == "unknown-scope":
        hello["scopes"] = ["core", "typo"]
    if args.mode == "partial-fields":
        hello["scopes"] = ["core", "hook"]
    for line in sys.stdin:
        request = json.loads(line)
        if request.get("op") == "hello":
            reply({"ok": True, "result": hello})
            if args.mode == "no-read":
                time.sleep(60)
        elif args.mode == "partial":
            sys.stdout.write('{"ok":')
            sys.stdout.flush()
            time.sleep(60)
        elif args.mode == "partial-fields":
            reply({"ok": True, "result": {"classification": "single-file", "conformant": True, "reason": "x"}})
        else:
            reply({"ok": True, "result": {}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
