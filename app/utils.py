"""
app/utils.py — Shared utilities used across all blueprints.

Includes:
- login_required decorator
- URL / value parsing helpers
- TLS config builder
- Safe count helper
- JSON serialiser fallback
- Allowed-value validator
"""

import re
from enum import Enum
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
from typing import Optional

from flask import session, request, redirect, url_for
from core.config_manager import ValidationError
from core.models import TLSConfig


# ─── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    """Redirect to /login when the user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('auth.login'))
        if session.get('must_change_password') and request.endpoint != 'auth.change_password':
            return redirect(url_for('auth.change_password'))
        return f(*args, **kwargs)
    return decorated


# ─── URL validation ────────────────────────────────────────────────────────────

def _validate_etcd_url(url: str) -> tuple[bool, str]:
    """Validate etcd URL shape with a clear message for the user."""
    if not url:
        return False, 'etcd URL is required.'
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        return False, 'etcd URL must start with http:// or https://'
    if not parsed.netloc:
        return False, 'etcd URL must include host and port (e.g. http://10.0.0.1:2379)'
    return True, ''


# ─── Routing rule helper ───────────────────────────────────────────────────────

def _extract_hostname_from_rule(rule: str) -> str:
    """Extract the first hostname from a Traefik Host(`example.com`) rule."""
    if not rule:
        return ''
    match = re.search(r'Host\(`([^`]+)`\)', rule)
    return match.group(1) if match else ''


# ─── Integer / CSV parsing ─────────────────────────────────────────────────────

def _parse_int(value: str, default: int = 0) -> int:
    """Parse *value* as int, returning *default* on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_csv(value: str) -> list[str]:
    """Split a comma-separated string into a cleaned list (no empty items)."""
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


# ─── List normalization ────────────────────────────────────────────────────────

def _normalize_multi(values: list[str]) -> list[str]:
    """Deduplicate and strip a list of strings while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        clean = (v or '').strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_allowed_values(selected: list[str], allowed: list[str], field_name: str) -> None:
    """Raise ValidationError when any submitted value is outside the allowed set."""
    invalid = sorted(set(selected) - set(allowed))
    if invalid:
        raise ValidationError(f'Invalid {field_name}: {", ".join(invalid)}')


# ─── TLS helpers ──────────────────────────────────────────────────────────────

def _tls_cert_resolver_value(tls: object) -> str:
    """Extract cert_resolver from a TLSConfig object or a raw dict."""
    if not tls:
        return ''
    if isinstance(tls, dict):
        return (
            tls.get('cert_resolver')
            or tls.get('certresolver')
            or tls.get('certResolver')
            or ''
        )
    return (
        getattr(tls, 'cert_resolver', '')
        or getattr(tls, 'certresolver', '')
        or ''
    )


def _build_tls_config(
    enable_tls: bool,
    cert_resolver: str,
    tls_options_value: str,
    tls_passthrough: bool = False,
) -> Optional[TLSConfig]:
    """Return a TLSConfig when TLS is active, or None otherwise."""
    if not (enable_tls or tls_passthrough):
        return None
    tls = TLSConfig(cert_resolver=cert_resolver)
    tls.options = tls_options_value
    return tls


# ─── Domain / cert resolver list ──────────────────────────────────────────────

def _available_cert_resolvers() -> list[str]:
    """Return sorted cert resolver names discovered from stored domains."""
    # Import here to always pick up the *current* config_manager reference.
    from app import globals as state  # noqa: PLC0415

    resolvers: set[str] = {'letsencrypt'}
    try:
        for domain in state.config_manager.get_domains():
            if getattr(domain, 'cert_resolver', ''):
                resolvers.add(domain.cert_resolver.strip())
    except Exception:
        pass
    return sorted(r for r in resolvers if r)


# ─── Safe aggregation helpers ─────────────────────────────────────────────────

def _safe_count(fn) -> int:
    """Call *fn()* and return len(result), or 0 if any exception is raised."""
    try:
        return len(fn())
    except Exception:
        return 0


def _safe_list(fn) -> list:
    """Call *fn()* and return the list, or [] if any exception is raised."""
    try:
        return fn()
    except Exception:
        return []


# ─── JSON serialisation ───────────────────────────────────────────────────────

def _json_default_serializer(value):
    """JSON *default=* handler for Enum, datetime, and set types."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, set):
        return list(value)
    return str(value)
