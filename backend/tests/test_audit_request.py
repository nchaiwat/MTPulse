import socket

import pytest
from starlette.requests import Request

from app.config import get_settings
from app.services.audit_request import request_details


@pytest.mark.parametrize(
    "peer,header,expected,source",
    [
        ("172.18.0.3", "192.168.10.99", "192.168.10.99", "trusted_proxy"),
        ("172.18.0.4", "192.168.10.99", "172.18.0.4", "server_observed"),
        ("172.18.0.3", "bad,spoofed", "172.18.0.3", "server_observed"),
    ],
)
def test_trust_only_configured_proxy(monkeypatch, peer, header, expected, source):
    monkeypatch.setenv("MTPULSE_AUDIT_PROXY_HOST", "web")
    get_settings.cache_clear()
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.18.0.3", 0))],
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/settings/ciam-sso/test-ad-login",
            "client": (peer, 1234),
            "headers": [(b"x-real-ip", header.encode()), (b"x-forwarded-for", b"spoofed")],
        }
    )
    try:
        result = request_details(request)
        assert result["ip"] == expected and result["ip_source"] == source
        assert result["peer_ip"] == peer and result["request_method"] == "POST"
        assert result["request_path"] == "/api/settings/ciam-sso/test-ad-login"
    finally:
        get_settings.cache_clear()


def test_proxy_dns_failure_does_not_trust_header(monkeypatch):
    monkeypatch.setenv("MTPULSE_AUDIT_PROXY_HOST", "web")
    get_settings.cache_clear()

    def unavailable(*a, **kw):
        raise socket.gaierror()

    monkeypatch.setattr(socket, "getaddrinfo", unavailable)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/local/login",
            "client": ("172.18.0.3", 1234),
            "headers": [(b"x-real-ip", b"192.168.10.99")],
        }
    )
    try:
        assert request_details(request)["ip"] == "172.18.0.3"
    finally:
        get_settings.cache_clear()
