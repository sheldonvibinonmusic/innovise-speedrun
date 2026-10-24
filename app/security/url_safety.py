"""URL Safety and SSRF Defense.

Implements strict validation:
- HTTP and HTTPS scheme enforcement (blocks file://, gopher://, ftp://, javascript:)
- Prevention of loopback, link-local, multicast, and private IP access (127.0.0.1, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.169.254)
- Domain scope enforcement (same-domain or allowed regulatory subdomains)
- DNS-based destination inspection before request dispatch
"""

import ipaddress
import socket
from typing import Optional, Set
from urllib.parse import urlparse


ALLOWED_SCHEMES = {"http", "https"}

# Known metadata endpoints and cloud services to explicitly block
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
}


def is_safe_ip(ip_str: str) -> bool:
    """Return False if IP address is private, loopback, link-local, multicast, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
        return True
    except ValueError:
        return False


def validate_url_safety(
    url: str,
    allowed_domains: Optional[Set[str]] = None,
    allow_private_for_tests: bool = False,
) -> bool:
    """Validate that a URL is syntactically safe, uses HTTP(S), and does not target internal network."""
    if not url or not isinstance(url, str):
        return False

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    hostname_lower = hostname.lower()

    if hostname_lower in BLOCKED_HOSTNAMES:
        return False

    # Check if hostname directly represents an IP literal
    try:
        ip = ipaddress.ip_address(hostname_lower)
        if not allow_private_for_tests and not is_safe_ip(str(ip)):
            return False
    except ValueError:
        # It's a domain name; resolve IP addresses to check for SSRF
        if not allow_private_for_tests:
            try:
                addr_info = socket.getaddrinfo(hostname_lower, None)
                for entry in addr_info:
                    resolved_ip = entry[4][0]
                    if not is_safe_ip(resolved_ip):
                        return False
            except socket.gaierror:
                # If DNS resolution fails, reject for security
                return False

    # Check domain allowlist/scope if provided
    if allowed_domains:
        match = any(
            hostname_lower == d.lower() or hostname_lower.endswith("." + d.lower())
            for d in allowed_domains
        )
        if not match:
            return False

    return True
