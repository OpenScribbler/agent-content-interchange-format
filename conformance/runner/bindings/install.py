"""TV-INSTALL bindings — entry-point resolution ([ACIF-INSTALL] §6–§11)."""

from __future__ import annotations

from typing import Any

from . import binding
from .common import (
    assert_diagnostic,
    assert_error,
    assert_result_field,
    diagnostics_for,
    result_for,
    send,
)
from ..vectors import Vector


def _resolve_request(case: dict[str, Any]) -> dict[str, Any]:
    inp: dict[str, Any] = {
        "provider": case["provider"],
        "content_type": case["content_type"],
        "content_name": case["content_name"],
        "home_dir": case["home_dir"],
        "project_root": case["project_root"],
    }
    for optional in ("scope", "entry", "overlay", "os", "appdata_dir"):
        if optional in case:
            inp[optional] = case[optional]
    return {"op": "resolve_install_targets", "input": inp}


@binding("TV-INSTALL-a")
def tv_install_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, _resolve_request(vector.data["input"]))
    assert_result_field(result, "matrix", response, "targets", vector.data["expect"]["targets"])
    return result


@binding("TV-INSTALL-b")
def tv_install_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, _resolve_request(case))
        assert_result_field(result, f"case_{idx}", response, "targets", exp[f"case_{idx}"]["targets"])
    return result


@binding("TV-INSTALL-c")
def tv_install_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    expected = vector.data["expect"]["error"]
    for idx, case in enumerate(vector.data["input"]["variants"], start=1):
        response = send(result, session, ctx, _resolve_request(case))
        assert_error(result, f"variant_{idx}", response, expected)
    return result


@binding("TV-INSTALL-d")
def tv_install_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, _resolve_request(vector.data["input"]))
    assert_error(result, "row", response, vector.data["expect"]["error"])
    return result


@binding("TV-INSTALL-e")
def tv_install_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, _resolve_request(case))
        expected = exp[f"case_{idx}"]
        if "error" in expected:
            assert_error(result, f"case_{idx}", response, expected["error"])
            if "params" in expected:
                assert_diagnostic(result, f"case_{idx}", response, expected["error"], expected["params"])
        else:
            assert_result_field(result, f"case_{idx}", response, "targets", expected["targets"])
            assert_diagnostic(result, f"case_{idx}", response, expected["diagnostic"])
    return result


@binding("TV-INSTALL-f")
def tv_install_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, _resolve_request(case))
        assert_result_field(result, f"case_{idx}", response, "targets", exp[f"case_{idx}"]["targets"])
    return result


@binding("TV-INSTALL-g")
def tv_install_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, _resolve_request(case))
        expected = exp[f"case_{idx}"]
        if "error" in expected:
            assert_error(result, f"case_{idx}", response, expected["error"])
        else:
            assert_result_field(result, f"case_{idx}", response, "targets", expected["targets"])
    return result


OVERRIDDEN = "acif.install.entry_point_overridden"


def _assert_overridden(result: Any, case: str, response: Any, expected: list[dict[str, Any]]) -> None:
    """Every entry_point_overridden the response carries, matched one to one
    against the expected params: a missing or an extra warning fails, and an
    expected param must be present (a null included). No other acif.install.*
    diagnostic may ride along, so a stray supersession warning fails too."""
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    diagnostics = diagnostics_for(response)
    observed = [d.get("params") for d in diagnostics if d.get("id") == OVERRIDDEN]
    unmatched = list(observed)
    passed = len(observed) == len(expected)
    if response.kind == "ok":
        stray = [
            d.get("id")
            for d in diagnostics
            if isinstance(d.get("id"), str) and d["id"].startswith("acif.install.") and d["id"] != OVERRIDDEN
        ]
        if stray:
            passed = False
            observed = {"overridden": observed, "unexpected_same_family": stray}
    for params in expected:
        match = next(
            (
                i
                for i, got in enumerate(unmatched)
                if isinstance(got, dict) and all(k in got and got[k] == v for k, v in params.items())
            ),
            None,
        )
        if match is None:
            passed = False
            break
        unmatched.pop(match)
    result.add_check(case, "diagnostic", {"id": OVERRIDDEN, "params": expected}, observed, passed)


@binding("TV-INSTALL-h")
def tv_install_h(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, _resolve_request(case))
        expected = exp[f"case_{idx}"]
        if "error" in expected:
            assert_error(result, f"case_{idx}", response, expected["error"])
            if "params" in expected:
                assert_diagnostic(result, f"case_{idx}", response, expected["error"], expected["params"])
            # A refusal writes nothing, so it discloses no override.
            _assert_overridden(result, f"case_{idx}", response, [])
        else:
            assert_result_field(result, f"case_{idx}", response, "targets", expected["targets"])
            _assert_overridden(result, f"case_{idx}", response, expected["overridden"])
    return result
