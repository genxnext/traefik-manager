"""
app/globals.py — Mutable shared state for the etcd client and config manager.

All blueprints reference etcd_client and config_manager through this module so
that a call to _reinit_etcd() is visible everywhere without stale references.

Usage in blueprints:
    from app import globals as state
    state.config_manager.list_routers()
"""

import os

import auth_db as _auth_db
from core.etcd_client import ETCDClient
from core.config_manager import ConfigManager

# ─── Active etcd connection ────────────────────────────────────────────────────

etcd_url: str = os.environ.get('ETCD_URL', 'http://localhost:2379')
etcd_client: ETCDClient = ETCDClient(etcd_url)
config_manager: ConfigManager = ConfigManager(etcd_client)


def _reinit_etcd(url: str) -> None:
    """Replace the global etcd client and config manager with a new URL."""
    global etcd_url, etcd_client, config_manager
    etcd_url = url
    etcd_client = ETCDClient(url)
    config_manager = ConfigManager(etcd_client)


# ─── Entrypoint option lists ───────────────────────────────────────────────────

HTTP_ENTRYPOINT_OPTIONS = [
    {'value': 'web',       'label': 'web (HTTP :80)'},
    {'value': 'websecure', 'label': 'websecure (HTTPS :443)'},
]

TCP_ENTRYPOINT_OPTIONS = [
    {'value': 'tcp',       'label': 'tcp (plain TCP)'},
    {'value': 'tcp-secure','label': 'tcp-secure (TLS TCP)'},
]

UDP_ENTRYPOINT_OPTIONS = [
    {'value': 'udp', 'label': 'udp (default UDP)'},
]

# ─── Nav / breadcrumb metadata ─────────────────────────────────────────────────
# Keys use Blueprint-qualified endpoint names (blueprint_name.view_function_name).

ENDPOINT_META: dict[str, dict[str, str]] = {
    # ── Common ──────────────────────────────────────────────────────────────
    'common.index':                     {'section': 'Dashboard', 'title': 'Overview'},
    'common.help_page':                 {'section': 'Config',    'title': 'Help'},
    'common.settings_connections':      {'section': 'Settings',  'title': 'etcd Connections'},
    'common.settings_connections_add':  {'section': 'Settings',  'title': 'Add etcd Connection'},
    'common.settings_connections_activate': {'section': 'Settings', 'title': 'Activate etcd Connection'},
    'common.settings_connections_delete':   {'section': 'Settings', 'title': 'Delete etcd Connection'},
    'common.settings_connections_edit':     {'section': 'Settings', 'title': 'Edit etcd Connection'},
    # ── Auth ─────────────────────────────────────────────────────────────────
    'auth.login':           {'section': 'Auth', 'title': 'Login'},
    'auth.logout':          {'section': 'Auth', 'title': 'Logout'},
    'auth.change_password': {'section': 'Auth', 'title': 'Change Password'},
    # ── HTTP – Routers ───────────────────────────────────────────────────────
    'http.list_routers':   {'section': 'HTTP', 'title': 'Routers'},
    'http.create_router':  {'section': 'HTTP', 'title': 'Create Router'},
    'http.edit_router':    {'section': 'HTTP', 'title': 'Edit Router'},
    'http.delete_router':  {'section': 'HTTP', 'title': 'Delete Router'},
    # ── HTTP – Services ──────────────────────────────────────────────────────
    'http.list_services':   {'section': 'HTTP', 'title': 'Services'},
    'http.service_detail':  {'section': 'HTTP', 'title': 'Service Details'},
    'http.create_service':  {'section': 'HTTP', 'title': 'Create Service'},
    'http.edit_service':    {'section': 'HTTP', 'title': 'Edit Service'},
    'http.delete_service':  {'section': 'HTTP', 'title': 'Delete Service'},
    # ── HTTP – Middlewares ───────────────────────────────────────────────────
    'http.list_middlewares':   {'section': 'HTTP', 'title': 'Middlewares'},
    'http.middleware_detail':  {'section': 'HTTP', 'title': 'Middleware Details'},
    'http.create_middleware':  {'section': 'HTTP', 'title': 'Create Middleware'},
    'http.edit_middleware':    {'section': 'HTTP', 'title': 'Edit Middleware'},
    'http.delete_middleware':  {'section': 'HTTP', 'title': 'Delete Middleware'},
    # ── HTTP – ServersTransports ─────────────────────────────────────────────
    'http.list_servers_transports':   {'section': 'HTTP', 'title': 'ServersTransport'},
    'http.create_servers_transport':  {'section': 'HTTP', 'title': 'Create ServersTransport'},
    'http.edit_servers_transport':    {'section': 'HTTP', 'title': 'Edit ServersTransport'},
    'http.delete_servers_transport':  {'section': 'HTTP', 'title': 'Delete ServersTransport'},
    # ── HTTP – Domains ───────────────────────────────────────────────────────
    'http.list_domains':      {'section': 'Config', 'title': 'Domains'},
    'http.create_domain':     {'section': 'Config', 'title': 'Create Domain'},
    'http.edit_domain':       {'section': 'Config', 'title': 'Edit Domain'},
    'http.set_default_domain':{'section': 'Config', 'title': 'Set Default Domain'},
    'http.delete_domain':     {'section': 'Config', 'title': 'Delete Domain'},
    # ── TCP – Routers ────────────────────────────────────────────────────────
    'tcp.list_tcp_routers':   {'section': 'TCP', 'title': 'Routers'},
    'tcp.create_tcp_router':  {'section': 'TCP', 'title': 'Create Router'},
    'tcp.edit_tcp_router':    {'section': 'TCP', 'title': 'Edit Router'},
    'tcp.delete_tcp_router':  {'section': 'TCP', 'title': 'Delete Router'},
    # ── TCP – Services ───────────────────────────────────────────────────────
    'tcp.list_tcp_services':   {'section': 'TCP', 'title': 'Services'},
    'tcp.create_tcp_service':  {'section': 'TCP', 'title': 'Create Service'},
    'tcp.edit_tcp_service':    {'section': 'TCP', 'title': 'Edit Service'},
    'tcp.delete_tcp_service':  {'section': 'TCP', 'title': 'Delete Service'},
    # ── TCP – Middlewares ────────────────────────────────────────────────────
    'tcp.list_tcp_middlewares':   {'section': 'TCP', 'title': 'Middlewares'},
    'tcp.create_tcp_middleware':  {'section': 'TCP', 'title': 'Create Middleware'},
    'tcp.edit_tcp_middleware':    {'section': 'TCP', 'title': 'Edit Middleware'},
    'tcp.delete_tcp_middleware':  {'section': 'TCP', 'title': 'Delete Middleware'},
    # ── UDP – Routers ────────────────────────────────────────────────────────
    'udp.list_udp_routers':   {'section': 'UDP', 'title': 'Routers'},
    'udp.create_udp_router':  {'section': 'UDP', 'title': 'Create Router'},
    'udp.edit_udp_router':    {'section': 'UDP', 'title': 'Edit Router'},
    'udp.delete_udp_router':  {'section': 'UDP', 'title': 'Delete Router'},
    # ── UDP – Services ───────────────────────────────────────────────────────
    'udp.list_udp_services':   {'section': 'UDP', 'title': 'Services'},
    'udp.create_udp_service':  {'section': 'UDP', 'title': 'Create Service'},
    'udp.edit_udp_service':    {'section': 'UDP', 'title': 'Edit Service'},
    'udp.delete_udp_service':  {'section': 'UDP', 'title': 'Delete Service'},
    # ── TLS – Options ────────────────────────────────────────────────────────
    'tls.list_tls_options':   {'section': 'TLS', 'title': 'Options'},
    'tls.create_tls_options': {'section': 'TLS', 'title': 'Create TLS Options'},
    'tls.edit_tls_options':   {'section': 'TLS', 'title': 'Edit TLS Options'},
    'tls.delete_tls_options': {'section': 'TLS', 'title': 'Delete TLS Options'},
    # ── TLS – Stores ─────────────────────────────────────────────────────────
    'tls.list_tls_stores':   {'section': 'TLS', 'title': 'Stores'},
    'tls.create_tls_store':  {'section': 'TLS', 'title': 'Create TLS Store'},
    'tls.edit_tls_store':    {'section': 'TLS', 'title': 'Edit TLS Store'},
    'tls.delete_tls_store':  {'section': 'TLS', 'title': 'Delete TLS Store'},
    # ── Config – Export / Import ─────────────────────────────────────────────
    'config.export_config':          {'section': 'Config', 'title': 'Export Configuration'},
    'config.export_config_download': {'section': 'Config', 'title': 'Export Config Download'},
    'config.export_full_backup':     {'section': 'Config', 'title': 'Export Full Backup'},
    'config.import_config':          {'section': 'Config', 'title': 'Import Configuration'},
    'config.import_full_backup':     {'section': 'Config', 'title': 'Import Full Backup'},
}
