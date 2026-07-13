from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import bindings
from .fixtures import EnvBlocked, FixtureContext, FixtureError, probe_environment
from .mock_http import MockHttpAuthority
from .protocol import AdapterSession, ProtocolError
from .report import VectorResult, build_report, make_out_of_scope
from .scopes import required_vector_ids, summarize_scopes
from .vectors import CatalogSet, load_catalogs

InvariantChecker = Callable[[list[Any], list[VectorResult]], None]
INVARIANT_CHECKERS: list[InvariantChecker] = []
INVARIANT_VECTOR_IDS: set[str] = set()


@dataclass
class RunOptions:
    adapter: str
    scopes: list[str] = field(default_factory=list)
    only: list[str] = field(default_factory=list)
    keep_fixtures: bool = False
    cwd: str | None = None


def run_conformance(options: RunOptions) -> dict[str, Any]:
    catalogs = load_catalogs()
    env = probe_environment()
    hello_result: dict[str, Any] | None = None
    hello_error: str | None = None
    adapter_protocol: int | None = None
    claimed_scopes: set[str] = set()
    all_observations: list[Any] = []

    session = AdapterSession(options.adapter, cwd=options.cwd)
    try:
        hello_result = session.start()
        adapter_protocol = hello_result.get("adapter_protocol")
        claimed_scopes = set(hello_result.get("scopes", []))
    except ProtocolError as exc:
        hello_error = str(exc)
        if exc.response and exc.response.result:
            adapter_protocol = exc.response.result.get("adapter_protocol")
            claimed_scopes = set(exc.response.result.get("scopes", []))
    except OSError as exc:
        hello_error = f"failed to start adapter: {exc}"

    requested_scopes = set(options.scopes)
    selected_scopes = requested_scopes if requested_scopes else claimed_scopes
    if hello_error is None:
        runnable_scopes = selected_scopes & claimed_scopes
    else:
        runnable_scopes = (selected_scopes & claimed_scopes) or selected_scopes
    in_scope_ids = required_vector_ids(runnable_scopes, claimed_scopes) if runnable_scopes else set()
    only_ids = set(options.only)

    unknown_only = sorted(only_ids - set(catalogs.by_id))
    if unknown_only:
        raise ValueError("unknown --only vector id(s): " + ", ".join(unknown_only))

    mock_http: MockHttpAuthority | None = None
    needs_mock_http = any(
        vector.id in in_scope_ids and vector.harness == "mock-transport" or vector.id == "TV-URI-t" and vector.id in in_scope_ids
        for vector in catalogs.vectors
    )
    if needs_mock_http and env.get("mock_http_tls", {}).get("ok"):
        try:
            mock_http = MockHttpAuthority()
            env["mock_http_tls"]["detail"] = env["mock_http_tls"]["detail"] + "; per-run CA generated"
        except EnvBlocked as exc:
            env["mock_http_tls"] = {"ok": False, "detail": str(exc)}

    vector_results: list[VectorResult] = []
    for vector in catalogs.vectors:
        if only_ids and vector.id not in only_ids:
            vector_results.append(make_out_of_scope(vector.id, vector.catalog, "not selected by --only"))
            continue
        if vector.id not in in_scope_ids:
            vector_results.append(make_out_of_scope(vector.id, vector.catalog, "not required by selected claimed scopes"))
            continue
        if hello_error is not None:
            vector_results.append(_harness_error(vector.id, vector.catalog, hello_error))
            continue
        if vector.harness not in {"static", "mock-transport", "mock-crawl"}:
            vector_results.append(_harness_error(vector.id, vector.catalog, f"unknown harness family {vector.harness!r}"))
            continue

        bind = bindings.get(vector.id)
        if bind is None:
            vector_results.append(_harness_error(vector.id, vector.catalog, "binding not implemented in this runner stage"))
            continue

        ctx = FixtureContext(env, keep_fixtures=options.keep_fixtures, mock_http=mock_http)
        try:
            result = bind(vector, session, ctx)
            if (
                result.status == "pass"
                and not result.checks
                and not result.vacuous
                and vector.id not in INVARIANT_VECTOR_IDS
            ):
                result.set_status("harness-error", "binding recorded no assertions")
        except EnvBlocked as exc:
            if "mock_http_tls" in exc.failed and "mock_http_tls" in env:
                env["mock_http_tls"]["ok"] = False
                detail = env["mock_http_tls"].get("detail", "")
                if "listener startup blocked" not in detail:
                    env["mock_http_tls"]["detail"] = detail + "; listener startup blocked"
            result = VectorResult(id=vector.id, catalog=vector.catalog, status="env-blocked", message=str(exc))
        except FixtureError as exc:
            result = _harness_error(vector.id, vector.catalog, f"fixture error: {exc}")
        except Exception as exc:
            result = _harness_error(vector.id, vector.catalog, f"binding raised {type(exc).__name__}: {exc}")
        finally:
            all_observations.extend(ctx.observations)
        result.fixture_paths = ctx.cleanup(result.status)
        vector_results.append(result)

    for checker in INVARIANT_CHECKERS:
        checker(all_observations, vector_results)

    vector_statuses = {result.id: result.status for result in vector_results}
    scope_status = summarize_scopes(
        requested_scopes=requested_scopes,
        claimed_scopes=claimed_scopes,
        vector_statuses=vector_statuses,
    )
    report = build_report(
        adapter_invocation=options.adapter,
        hello_result=hello_result,
        hello_error=hello_error,
        adapter_protocol=adapter_protocol,
        catalog_hashes=catalogs.catalog_hashes,
        binding_set_hash=bindings.binding_set_hash(),
        env_probes=env,
        requested_scopes=sorted(requested_scopes),
        claimed_scopes=sorted(claimed_scopes),
        selected_scopes=sorted(selected_scopes),
        scope_status=scope_status,
        vector_results=vector_results,
    )
    if mock_http is not None:
        mock_http.cleanup()
    session.close()
    return report


def _harness_error(vector_id: str, catalog: str, message: str) -> VectorResult:
    return VectorResult(id=vector_id, catalog=catalog, status="harness-error", message=message)
