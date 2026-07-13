from __future__ import annotations

import http.server
import shutil
import ssl
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from .fixtures import EnvBlocked


@dataclass(frozen=True)
class Route:
    scheme: str
    host: str
    path: str
    status: int
    location: str | None = None


class MockHttpAuthority:
    def __init__(self) -> None:
        self.openssl = shutil.which("openssl")
        if self.openssl is None:
            raise EnvBlocked(["mock_http_tls"])
        self.root = Path(tempfile.mkdtemp(prefix="acif-mock-http-")).resolve()
        self.ca_key = self.root / "ca.key"
        self.ca_bundle = self.root / "ca.pem"
        self._leafs: dict[str, tuple[Path, Path]] = {}
        self._run(
            [
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-keyout",
                str(self.ca_key),
                "-out",
                str(self.ca_bundle),
                "-subj",
                "/CN=ACIF conformance mock CA",
                "-addext",
                "basicConstraints=critical,CA:TRUE",
                "-addext",
                "keyUsage=critical,keyCertSign,cRLSign",
            ]
        )

    def start_vector(self, request: str, transport: list[dict[str, Any]] | str) -> "MockDouble":
        return self.start_routes(_routes_for_transport(request, transport))

    def start_cases(self, cases: list[dict[str, Any]]) -> "MockDouble":
        routes: list[Route] = []
        for case in cases:
            routes.extend(_routes_for_transport(case["request"], case["transport"]))
        return self.start_routes(routes)

    def start_crawl(self, request: str, transport_each: list[dict[str, Any]], pass_index: int) -> "MockDouble":
        return self.start_routes(_routes_for_crawl(request, transport_each, pass_index))

    def start_routes(self, routes: list[Route]) -> "MockDouble":
        double = MockDouble(self, str(self.ca_bundle))
        double.set_routes(routes)
        return double

    def leaf_for(self, host: str) -> tuple[Path, Path]:
        if host not in self._leafs:
            self._leafs[host] = self._generate_leaf(host)
        return self._leafs[host]

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _generate_leaf(self, host: str) -> tuple[Path, Path]:
        safe = host.replace("*", "_").replace(".", "_")
        key = self.root / f"{safe}.key"
        csr = self.root / f"{safe}.csr"
        cert = self.root / f"{safe}.pem"
        cfg = self.root / f"{safe}.cnf"
        cfg.write_text(
            "\n".join(
                [
                    "[req]",
                    "distinguished_name=req_distinguished_name",
                    "req_extensions=req_ext",
                    "prompt=no",
                    "[req_distinguished_name]",
                    f"CN={host}",
                    "[req_ext]",
                    f"subjectAltName=DNS:{host}",
                    "basicConstraints=CA:FALSE",
                    "keyUsage=digitalSignature,keyEncipherment",
                    "extendedKeyUsage=serverAuth",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self._run(
            [
                "req",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(csr),
                "-subj",
                f"/CN={host}",
                "-config",
                str(cfg),
            ]
        )
        self._run(
            [
                "x509",
                "-req",
                "-in",
                str(csr),
                "-CA",
                str(self.ca_bundle),
                "-CAkey",
                str(self.ca_key),
                "-CAcreateserial",
                "-out",
                str(cert),
                "-days",
                "1",
                "-sha256",
                "-extensions",
                "req_ext",
                "-extfile",
                str(cfg),
            ]
        )
        return cert, key

    def _run(self, args: list[str]) -> None:
        assert self.openssl is not None
        try:
            subprocess.run(
                [self.openssl, *args],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise EnvBlocked(["mock_http_tls"]) from exc


class MockDouble:
    def __init__(self, authority: MockHttpAuthority, ca_bundle: str) -> None:
        self.authority = authority
        self.ca_bundle = ca_bundle
        self.resolve: dict[str, str] = {}
        self._routes: dict[tuple[str, str, str], Route] = {}
        self._servers: dict[tuple[str, str], http.server.ThreadingHTTPServer] = {}
        self._threads: list[threading.Thread] = []

    def set_routes(self, routes: list[Route]) -> None:
        self._routes = {(route.scheme, route.host, route.path): route for route in routes}
        needed = {(route.scheme, route.host) for route in routes}
        for scheme, host in sorted(needed):
            if (scheme, host) not in self._servers:
                self._start_server(scheme, host)

    def set_crawl(self, request: str, transport_each: list[dict[str, Any]], pass_index: int) -> None:
        self.set_routes(_routes_for_crawl(request, transport_each, pass_index))

    def close(self) -> None:
        for server in self._servers.values():
            server.shutdown()
            server.server_close()
        self._servers.clear()
        self.resolve.clear()

    def _start_server(self, scheme: str, host: str) -> None:
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _handler_class(self))
        except OSError as exc:
            raise EnvBlocked(["mock_http_tls"]) from exc
        server.acif_scheme = scheme  # type: ignore[attr-defined]
        server.acif_host = host  # type: ignore[attr-defined]
        if scheme == "https":
            cert, key = self.authority.leaf_for(host)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(cert), str(key))
            try:
                server.socket = context.wrap_socket(server.socket, server_side=True)
            except OSError as exc:
                server.server_close()
                raise EnvBlocked(["mock_http_tls"]) from exc
        port = server.server_address[1]
        self._servers[(scheme, host)] = server
        self.resolve[host] = f"127.0.0.1:{port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._threads.append(thread)


def _handler_class(double: MockDouble) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            scheme = self.server.acif_scheme  # type: ignore[attr-defined]
            host = self.server.acif_host  # type: ignore[attr-defined]
            path = urlsplit(self.path).path or "/"
            route = double._routes.get((scheme, host, path))
            if route is None:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"not found\n")
                return
            self.send_response(route.status)
            if route.location is not None:
                self.send_header("Location", route.location)
            self.end_headers()
            if route.status == 200:
                self.wfile.write(b"ok\n")

        def log_message(self, format: str, *args: Any) -> None:
            del format, args

    return Handler


def _routes_for_transport(request: str, transport: list[dict[str, Any]] | str) -> list[Route]:
    if transport == "eleven-hop-chain":
        return _eleven_hop_chain(request)
    if transport == "two-node-301-loop":
        return _two_node_loop(request)
    if not isinstance(transport, list):
        raise ValueError(f"unknown transport script {transport!r}")
    routes: list[Route] = []
    current = request
    for step in transport:
        parts = urlsplit(current)
        location = step.get("location")
        routes.append(Route(parts.scheme, parts.hostname or "", parts.path or "/", int(step["status"]), location))
        if location is not None:
            current = urljoin(current, location)
            if urlsplit(current).scheme == "http" and not any(s.get("status") == 200 for s in transport):
                target = urlsplit(current)
                routes.append(Route("http", target.hostname or "", target.path or "/", 200, None))
        else:
            break
    return routes


def _eleven_hop_chain(request: str) -> list[Route]:
    parts = urlsplit(request)
    host = parts.hostname or ""
    routes: list[Route] = []
    for idx in range(11):
        routes.append(Route("https", host, f"/{idx}", 301, f"https://{host}/{idx + 1}"))
    routes.append(Route("https", host, "/11", 200, None))
    return routes


def _two_node_loop(request: str) -> list[Route]:
    first = urlsplit(request)
    second_host = "b.example.com" if first.hostname != "b.example.com" else "a.example.com"
    path = first.path or "/loop"
    return [
        Route("https", first.hostname or "", path, 301, f"https://{second_host}{path}"),
        Route("https", second_host, path, 301, request),
    ]


def _routes_for_crawl(request: str, transport_each: list[dict[str, Any]], pass_index: int) -> list[Route]:
    routes: list[Route] = []
    current = request
    for step in transport_each:
        materialized = dict(step)
        if isinstance(materialized.get("location"), str):
            materialized["location"] = materialized["location"].replace("{random}", str(pass_index))
        parts = urlsplit(current)
        routes.append(
            Route(
                parts.scheme,
                parts.hostname or "",
                parts.path or "/",
                int(materialized["status"]),
                materialized.get("location"),
            )
        )
        if materialized.get("location") is not None:
            current = urljoin(current, materialized["location"])
        else:
            break
    return routes
