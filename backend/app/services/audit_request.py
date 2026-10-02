"""Audit provenance from a known reverse proxy, never arbitrary forwarded headers."""

import socket
from ipaddress import ip_address

from fastapi import Request

from app.config import get_settings


def request_details(request: Request) -> dict:
    peer = request.client.host if request.client else None
    result = {
        "ip": peer,
        "peer_ip": peer,
        "ip_source": "server_observed",
        "request_method": request.method,
        "request_path": request.url.path,
    }
    proxy_host = get_settings().audit_proxy_host
    if not proxy_host or not peer:
        return result
    try:
        # Docker DNS identifies the configured web service across container recreation.
        trusted = {
            item[4][0] for item in socket.getaddrinfo(proxy_host, None, type=socket.SOCK_STREAM)
        }
        if peer in trusted:
            # nginx overwrites this header with its TCP remote_addr.
            forwarded = str(ip_address(request.headers.get("x-real-ip", "")))
            result.update(ip=forwarded, ip_source="trusted_proxy")
    except (OSError, ValueError):
        pass  # Fail closed: preserve peer rather than guess an end-user address.
    return result
