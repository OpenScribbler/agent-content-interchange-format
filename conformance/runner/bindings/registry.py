from __future__ import annotations

from typing import Any

from . import binding
from .common import (
    ABSENT,
    assert_absent,
    assert_diagnostic,
    assert_error,
    assert_relation,
    assert_result_field,
    assert_value,
    derive_url_name,
    evaluate_freshness,
    fetch_uri,
    hash_value,
    ingest,
    normalize_uri,
    result_for,
    send,
)
from ..fixtures import EnvBlocked
from ..report import VectorResult
from ..vectors import Vector

SOURCE_STATUS_VALUES = {"live", "moved", "gone", "unreachable"}


def _all_ok(responses: list[Any]) -> bool:
    return all(response.kind == "ok" for response in responses)


def _assert_uri_result(result: VectorResult, case: str, response: Any, expected: dict[str, Any]) -> None:
    if "error" in expected:
        assert_error(result, case, response, expected["error"])
    else:
        assert_result_field(result, case, response, "source_uri", expected["source_uri"])


def _mock_fetch(result: VectorResult, vector: Vector, session: Any, ctx: Any, case_input: dict[str, Any]) -> Any:
    mock_http = getattr(ctx, "mock_http", None)
    if mock_http is None:
        if hasattr(ctx, "env"):
            raise EnvBlocked(["mock_http_tls"])
        response = send(result, session, ctx, fetch_uri(case_input["request"], "", {}))
        return response
    double = mock_http.start_vector(case_input["request"], case_input["transport"])
    try:
        return send(result, session, ctx, fetch_uri(case_input["request"], double.ca_bundle, double.resolve))
    finally:
        double.close()


@binding("TV-URI-a")
def tv_uri_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, normalize_uri(vector.data["input"]["uri"]))
    assert_result_field(result, "uri", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-b")
def tv_uri_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, normalize_uri(vector.data["input"]["uri"]))
    assert_result_field(result, "uri", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-c")
def tv_uri_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, normalize_uri(vector.data["input"]["uri"]))
    assert_result_field(result, "uri", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-d")
def tv_uri_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, normalize_uri(vector.data["input"]["uri"]))
    assert_result_field(result, "uri", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-e")
def tv_uri_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, normalize_uri(vector.data["input"]["uri"]))
    assert_result_field(result, "uri", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-f")
def tv_uri_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, normalize_uri(case["uri"]))
        assert_result_field(result, f"case_{idx}", response, "source_uri", vector.data["expect"][f"case_{idx}"]["source_uri"])
    return result


@binding("TV-URI-g")
def tv_uri_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, normalize_uri(vector.data["input"]["uri"]))
    assert_result_field(result, "uri", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-h")
def tv_uri_h(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, normalize_uri(vector.data["input"]["uri"]))
    assert_result_field(result, "uri", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-i")
def tv_uri_i(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, normalize_uri(case["uri"]))
        _assert_uri_result(result, f"case_{idx}", response, vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-URI-j")
def tv_uri_j(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, normalize_uri(case["uri"]))
        assert_error(result, f"case_{idx}", response, vector.data["expect"][f"case_{idx}"]["error"])
    return result


@binding("TV-URI-k")
def tv_uri_k(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, normalize_uri(vector.data["input"]["uri"]))
    assert_error(result, "uri", response, vector.data["expect"]["error"])
    return result


@binding("TV-URI-l")
def tv_uri_l(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = _mock_fetch(result, vector, session, ctx, vector.data["input"])
    assert_result_field(result, "transport", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-l2")
def tv_uri_l2(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = _mock_fetch(result, vector, session, ctx, vector.data["input"])
    assert_result_field(result, "transport", response, "source_uri", vector.data["expect"]["source_uri"])
    return result


@binding("TV-URI-m")
def tv_uri_m(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = _mock_fetch(result, vector, session, ctx, vector.data["input"])
    assert_error(result, "transport", response, vector.data["expect"]["error"])
    return result


@binding("TV-URI-n")
def tv_uri_n(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    mock_http = getattr(ctx, "mock_http", None)
    if mock_http is None:
        if hasattr(ctx, "env"):
            raise EnvBlocked(["mock_http_tls"])
        for idx, case in enumerate(vector.data["input"]["cases"], start=1):
            response = send(result, session, ctx, fetch_uri(case["request"], "", {}))
            assert_error(result, f"case_{idx}", response, vector.data["expect"]["error"])
        return result
    double = mock_http.start_cases(vector.data["input"]["cases"])
    try:
        for idx, case in enumerate(vector.data["input"]["cases"], start=1):
            response = send(result, session, ctx, fetch_uri(case["request"], double.ca_bundle, double.resolve))
            assert_error(result, f"case_{idx}", response, vector.data["expect"]["error"])
    finally:
        double.close()
    return result


@binding("TV-URI-o")
def tv_uri_o(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(result, session, ctx, derive_url_name(inp["uri"], inp["body_classification"]))
    assert_result_field(result, "uri", response, "url_derived_name", vector.data["expect"]["url_derived_name"])
    return result


@binding("TV-URI-o2")
def tv_uri_o2(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, derive_url_name(inp["uri"], inp["body_classification"], inp["frontmatter_name"]))
    assert_result_field(result, "uri", response, "url_derived_name", exp["recorded"][0])
    if response.kind == "ok":
        recorded = [hash_value(response, "url_derived_name"), inp["frontmatter_name"]]
        result.add_check("uri", "recorded", exp["recorded"], recorded, recorded == exp["recorded"])
    assert_diagnostic(
        result,
        "uri",
        response,
        exp["diagnostic"],
        {"url_derived_name": exp["recorded"][0], "declared_name": exp["recorded"][1]},
    )
    return result


@binding("TV-URI-p")
def tv_uri_p(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(result, session, ctx, derive_url_name(inp["uri"], inp["body_classification"]))
    assert_error(result, "uri", response, vector.data["expect"]["error"])
    return result


@binding("TV-URI-q")
def tv_uri_q(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, derive_url_name(inp["uri"], inp["body_classification"]))
    assert_result_field(result, "uri", response, "conformant", exp["conformant"])
    assert_result_field(result, "uri", response, "url_derived_name", exp["url_derived_name"])
    return result


@binding("TV-URI-r")
def tv_uri_r(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    for idx, uri in enumerate(vector.data["input"]["uris"], start=1):
        first = send(result, session, ctx, normalize_uri(uri))
        normalized = hash_value(first, "source_uri")
        second = send(result, session, ctx, normalize_uri(normalized if isinstance(normalized, str) else uri))
        if _all_ok([first, second]):
            observed = [hash_value(first, "source_uri"), hash_value(second, "source_uri")]
            assert_relation(result, f"uri_{idx}", "normalize_normalize_equals_normalize", exp["normalize_normalize_equals_normalize"], observed, observed[0] == observed[1])
        else:
            assert_result_field(result, f"uri_{idx}", first, "source_uri", "normalized")
    return result


@binding("TV-URI-s")
def tv_uri_s(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    responses = [
        send(
            result,
            session,
            ctx,
            ingest("skill", body_root=ctx.materialize(inp["body"]["files"]), entry_file="SKILL.md", context=record),
        )
        for record in inp["records"]
    ]
    if _all_ok(responses):
        body_hashes = [hash_value(response, "body_hash") for response in responses]
        metadata_hashes = [hash_value(response, "metadata_hash") for response in responses]
        assert_relation(result, "records", "body_hash_identical", vector.data["expect"]["body_hash_identical"], body_hashes, len(set(body_hashes)) == 1)
        assert_relation(result, "records", "metadata_hash_identical", vector.data["expect"]["metadata_hash_identical"], metadata_hashes, len(set(metadata_hashes)) == 1)
    else:
        for idx, response in enumerate(responses, start=1):
            assert_result_field(result, f"record_{idx}", response, "body_hash", "present")
    return result


@binding("TV-URI-t")
def tv_uri_t(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    mock_http = getattr(ctx, "mock_http", None)
    if mock_http is None:
        if hasattr(ctx, "env"):
            raise EnvBlocked(["mock_http_tls"])
        responses = [send(result, session, ctx, fetch_uri(vector.data["input"]["request"], "", {})) for _ in range(2)]
    else:
        double = mock_http.start_crawl(vector.data["input"]["request"], vector.data["input"]["transport_each"], 1)
        try:
            first = send(result, session, ctx, fetch_uri(vector.data["input"]["request"], double.ca_bundle, double.resolve))
            double.set_crawl(vector.data["input"]["request"], vector.data["input"]["transport_each"], 2)
            second = send(result, session, ctx, fetch_uri(vector.data["input"]["request"], double.ca_bundle, double.resolve))
            responses = [first, second]
        finally:
            double.close()
    if _all_ok(responses):
        observed = [hash_value(response, "source_uri") for response in responses]
        expected = vector.data["expect"]["source_uri_byte_identical_across_crawls"]
        assert_relation(result, "crawls", "source_uri_byte_identical_across_crawls", expected, observed, observed[0] == observed[1])
    else:
        for idx, response in enumerate(responses):
            if response.kind != "ok":
                assert_result_field(result, f"crawls[{idx}]", response, "source_uri", "<ok response>")
    return result


@binding("TV-URI-u")
def tv_uri_u(vector: Vector, session: Any, ctx: Any):
    del session, ctx
    result = result_for(vector)
    for value in vector.data["expect"]["if_emitted"]["value_in"]:
        result.add_check_equivalent(value)
    return result


@binding("TV-URI-v")
def tv_uri_v(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(
        result,
        session,
        ctx,
        ingest("skill", sidecar=vector.data["input"]["record"], context={"validation_surface": "registry_emit"}),
    )
    assert_error(result, "record", response, vector.data["expect"]["error"])
    return result


@binding("TV-FRESH-a")
def tv_fresh_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(
        result,
        session,
        ctx,
        evaluate_freshness(
            inp["record"],
            consumer_clock=inp["consumer_clock"],
            attestation_evaluation=inp["attestation_evaluation"],
        ),
    )
    assert_result_field(result, "record", response, "staleness", exp["staleness"])
    assert_result_field(result, "record", response, "trust_tier", exp["trust_tier"])
    if response.kind == "ok":
        warnings = hash_value(response, "warnings")
        warn_not_refuse = bool(warnings) and hash_value(response, "install") != "refuse"
        observed_policy = exp["default_policy"] if warn_not_refuse else {"warnings": warnings, "install": hash_value(response, "install")}
        result.add_check("record", "default_policy", exp["default_policy"], observed_policy, observed_policy == exp["default_policy"])
    result.add_check_equivalent(exp["default_policy"])
    assert_absent(result, "record", response, "combined_scalar", exp["combined_scalar_present"])
    return result


@binding("TV-FRESH-b")
def tv_fresh_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(
        result,
        session,
        ctx,
        evaluate_freshness(
            inp["record"],
            consumer_clock=inp["consumer_clock"],
            attestation_evaluation=inp["attestation_evaluation"],
        ),
    )
    assert_result_field(result, "record", response, "staleness", vector.data["expect"]["staleness"])
    assert_result_field(result, "record", response, "trust_tier", vector.data["expect"]["trust_tier"])
    return result


@binding("TV-FRESH-c")
def tv_fresh_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    responses = [
        send(result, session, ctx, evaluate_freshness(inp["record"], attestation_system=state))
        for state in inp["attestation_system"]
    ]
    exp = vector.data["expect"]
    if _all_ok(responses):
        response_hashes = [hash_value(response, "response_hash") for response in responses]
        assert_relation(result, "attestation_system", "registry_response_byte_identical", exp["registry_response_byte_identical"], response_hashes, response_hashes[0] == response_hashes[1])
        staleness_values = [hash_value(response, "staleness") for response in responses]
        assert_relation(result, "attestation_system", "staleness_unaffected", exp["staleness_unaffected"], staleness_values, staleness_values[0] == staleness_values[1])
    assert_result_field(result, "unreachable", responses[-1], "trust_tier", exp["trust_tier_when_unreachable"])
    return result


@binding("TV-FRESH-d")
def tv_fresh_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    for idx, clock in enumerate(inp["clocks"], start=1):
        response = send(result, session, ctx, evaluate_freshness(inp["record"], consumer_clock=clock))
        assert_result_field(result, f"clock_{idx}", response, "staleness", vector.data["expect"][f"clock_{idx}"])
    return result


@binding("TV-FRESH-e")
def tv_fresh_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    malformed = send(result, session, ctx, evaluate_freshness(inp["malformed"], consumer_clock=inp["consumer_clock"]))
    assert_error(result, "malformed", malformed, vector.data["expect"]["malformed"]["error"])
    past = send(result, session, ctx, evaluate_freshness(inp["past"], consumer_clock=inp["consumer_clock"]))
    assert_result_field(result, "past", past, "conformant", vector.data["expect"]["past"]["conformant"])
    assert_result_field(result, "past", past, "staleness", vector.data["expect"]["past"]["staleness"])
    return result


@binding("TV-FRESH-f")
def tv_fresh_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, evaluate_freshness(vector.data["input"]["record"]))
    assert_result_field(result, "record", response, "conformant", vector.data["expect"]["conformant"])
    return result


@binding("TV-FRESH-g")
def tv_fresh_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(
        result,
        session,
        ctx,
        evaluate_freshness(
            inp["record"],
            consumer_clock=inp["consumer_clock"],
            declared_tolerance_seconds=inp["declared_tolerance_seconds"],
        ),
    )
    assert_result_field(result, "record", response, "staleness", vector.data["expect"]["staleness"])
    return result


@binding("TV-FRESH-h")
def tv_fresh_h(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for policy in inp["policies"]:
        response = send(result, session, ctx, evaluate_freshness(inp["record"], consumer_clock=inp["consumer_clock"], policies=[policy]))
        expected = exp["default"] if policy == "default" else exp["opt_in"]
        assert_result_field(result, policy, response, "install", expected["install"])
        if "state_flag" in expected:
            assert_result_field(result, policy, response, "staleness", expected["state_flag"])
        if expected.get("warn") is True and response.kind == "ok":
            warnings = hash_value(response, "warnings")
            assert_relation(result, policy, "warn", expected["warn"], warnings, bool(warnings))
    return result


@binding("TV-FRESH-i")
def tv_fresh_i(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, evaluate_freshness(inp["record"], consumer_clock=inp["consumer_clock"]))
    assert_result_field(result, "record", response, "staleness", exp["staleness"])
    assert_result_field(result, "record", response, "trust_tier", exp["trust_tier"])
    if response.kind == "ok":
        warnings = hash_value(response, "warnings")
        observed = "none" if warnings in (ABSENT, [], None) else warnings
        result.add_check("record", "warnings", exp["warnings"], observed, observed == exp["warnings"])
    else:
        assert_result_field(result, "record", response, "warnings", exp["warnings"])
    return result


@binding("TV-FRESH-j")
def tv_fresh_j(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    crawl_1 = send(
        result,
        session,
        ctx,
        evaluate_freshness(inp["crawl_1"], consumer_clock=inp["consumer_clock"], attestation_evaluation=inp["attestation_evaluation"]),
    )
    crawl_2 = send(
        result,
        session,
        ctx,
        evaluate_freshness(inp["crawl_2"], consumer_clock=inp["consumer_clock"], attestation_evaluation=inp["attestation_evaluation"]),
    )
    del crawl_1
    assert_result_field(result, "crawl_2", crawl_2, "staleness", vector.data["expect"]["staleness_after_crawl_2"])
    assert_result_field(result, "crawl_2", crawl_2, "trust_tier", vector.data["expect"]["trust_tier"])
    return result


@binding("TV-FRESH-k")
def tv_fresh_k(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(
        result,
        session,
        ctx,
        evaluate_freshness(
            inp["record"],
            consumer_clock=inp["consumer_clock"],
            extra={"implementation_behavior": inp["implementation_behavior"]},
        ),
    )
    assert_result_field(result, "record", response, "conformant", vector.data["expect"]["conformant"])
    return result


def _source_status_invariant(observations: list[Any], vector_results: list[VectorResult]) -> None:
    rows = {row.id: row for row in vector_results}
    row = rows.get("TV-URI-u")
    if row is None or row.status == "out-of-scope":
        return
    observed: list[Any] = []
    for response in observations:
        if response.kind != "ok" or not isinstance(response.result, dict):
            continue
        if "source_status" in response.result:
            observed.append(response.result["source_status"])
            row.add_check(
                getattr(response, "_acif_vector_id", "response"),
                "source_status",
                sorted(SOURCE_STATUS_VALUES),
                response.result["source_status"],
                response.result["source_status"] in SOURCE_STATUS_VALUES,
            )
    if not observed:
        row.vacuous = True


def _register_invariant() -> None:
    from .. import run as runner_run

    if _source_status_invariant not in runner_run.INVARIANT_CHECKERS:
        runner_run.INVARIANT_CHECKERS.append(_source_status_invariant)
    runner_run.INVARIANT_VECTOR_IDS.add("TV-URI-u")


_register_invariant()
