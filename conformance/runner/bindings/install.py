"""TV-INSTALL bindings — entry-point resolution ([ACIF-INSTALL] §6–§11)."""

from __future__ import annotations

from typing import Any

from . import binding
from .common import (
    assert_diagnostic,
    assert_error,
    assert_result_field,
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
    for optional in ("scope", "entry"):
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
