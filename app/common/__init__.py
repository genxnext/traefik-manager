"""
app/common.py — Common / Dashboard Blueprint.

Routes: /, /help, /settings/connections (and sub-routes)
Also registers app-wide before_request and context_processor hooks.
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session,
)

import auth_db as _auth_db
from app import globals as state
from app.utils import login_required, _validate_etcd_url, _safe_count, _safe_list

bp = Blueprint('common', __name__, template_folder='templates')


# ─── App-wide request hooks ────────────────────────────────────────────────────

@bp.before_app_request
def check_auth_and_sync():
    """Enforce login and keep the global etcd client in sync with the active DB connection."""
    open_endpoints = {'auth.login', 'auth.logout', 'static', 'health.health'}
    if request.endpoint in open_endpoints:
        return

    if 'username' not in session:
        return redirect(url_for('auth.login'))

    if session.get('must_change_password') and request.endpoint != 'auth.change_password':
        return redirect(url_for('auth.change_password'))

    # Sync etcd connection when the active profile changes in the DB.
    try:
        active = _auth_db.get_active_connection()
        if active and active['url'] != state.etcd_url:
            state._reinit_etcd(active['url'])
    except Exception:
        pass  # Non-fatal: continue with current client


@bp.app_context_processor
def inject_nav_status():
    """Inject nav state and breadcrumb info into every template context."""
    try:
        nav_etcd_healthy = state.etcd_client.health_check()
    except Exception:
        nav_etcd_healthy = False

    try:
        conn = _auth_db.get_active_connection()
        nav_conn_name = conn['name'] if conn else 'Default'
        nav_conn_url  = conn['url']  if conn else state.etcd_url
    except Exception:
        nav_conn_name = 'Default'
        nav_conn_url  = state.etcd_url

    endpoint = request.endpoint or ''
    meta = state.ENDPOINT_META.get(endpoint, {})
    auto_section = meta.get('section')
    auto_title   = meta.get('title') or endpoint.replace('_', ' ').title() if endpoint else 'Dashboard'

    return {
        'nav_etcd_healthy':       nav_etcd_healthy,
        'nav_conn_name':          nav_conn_name,
        'nav_conn_url':           nav_conn_url,
        'current_user':           session.get('username', ''),
        'auto_breadcrumb_section': auto_section,
        'auto_breadcrumb_title':  auto_title,
    }


# ─── Dashboard ─────────────────────────────────────────────────────────────────

@bp.route('/')
@login_required
def index():
    """Home dashboard: counts for all resource types and recent routers."""
    cm = state.config_manager

    router_count      = _safe_count(cm.list_routers)
    service_count     = _safe_count(cm.list_services)
    middleware_count  = _safe_count(cm.list_middlewares)
    domain_count      = _safe_count(cm.get_domains)
    tcp_router_count  = _safe_count(cm.list_tcp_routers)
    tcp_service_count = _safe_count(cm.list_tcp_services)
    udp_router_count  = _safe_count(cm.list_udp_routers)
    udp_service_count = _safe_count(cm.list_udp_services)
    tls_options_count = _safe_count(cm.list_tls_options)
    tls_store_count   = _safe_count(cm.list_tls_stores)
    st_count          = _safe_count(cm.list_servers_transports)

    try:
        etcd_healthy = state.etcd_client.health_check()
    except Exception:
        etcd_healthy = False

    recent_routers = _safe_list(cm.list_routers)

    return render_template(
        'common/index.html',
        router_count=router_count,
        service_count=service_count,
        middleware_count=middleware_count,
        domain_count=domain_count,
        tcp_router_count=tcp_router_count,
        tcp_service_count=tcp_service_count,
        udp_router_count=udp_router_count,
        udp_service_count=udp_service_count,
        tls_options_count=tls_options_count,
        tls_store_count=tls_store_count,
        st_count=st_count,
        etcd_healthy=etcd_healthy,
        recent_routers=recent_routers,
        etcd_url_display=state.etcd_url,
    )


@bp.route('/help')
@login_required
def help_page():
    """Comprehensive user help page."""
    return render_template('common/help.html')


# ─── etcd Connection Settings ──────────────────────────────────────────────────

@bp.route('/settings/connections')
@login_required
def settings_connections():
    """List all saved etcd connection profiles."""
    try:
        connections = _auth_db.list_connections()
        return render_template('common/settings.html', connections=connections, load_error=None)
    except Exception:
        return render_template(
            'common/settings.html',
            connections=[],
            load_error='Unable to load connection settings. Check database permissions and retry.',
        )


@bp.route('/settings/connections/add', methods=['POST'])
@login_required
def settings_connections_add():
    """Save a new etcd connection profile."""
    name = request.form.get('name', '').strip()
    url  = request.form.get('url', '').strip()
    desc = request.form.get('description', '').strip()

    if not name:
        flash('Connection name is required.', 'danger')
    else:
        valid, message = _validate_etcd_url(url)
        if not valid:
            flash(message, 'danger')
        else:
            try:
                _auth_db.add_connection(name, url, desc)
                flash(f'Connection "{name}" added.', 'success')
            except Exception:
                flash('Could not add connection. Please verify database write permissions and try again.', 'danger')

    return redirect(url_for('common.settings_connections'))


@bp.route('/settings/connections/activate/<int:conn_id>', methods=['POST'])
@login_required
def settings_connections_activate(conn_id):
    """Set a saved profile as the active etcd connection."""
    try:
        _auth_db.activate_connection(conn_id)
        active = _auth_db.get_active_connection()
        if active and active.get('url'):
            state._reinit_etcd(active['url'])
            flash(f'Switched to connection "{active["name"]}".', 'success')
        else:
            flash('Connection activated, but active target could not be resolved.', 'warning')
    except Exception:
        flash('Could not activate selected connection. Please retry.', 'danger')

    return redirect(url_for('common.settings_connections'))


@bp.route('/settings/connections/delete/<int:conn_id>', methods=['POST'])
@login_required
def settings_connections_delete(conn_id):
    """Delete a saved etcd connection profile."""
    try:
        _auth_db.delete_connection(conn_id)
        flash('Connection deleted.', 'success')
    except Exception as exc:
        if 'only connection' in str(exc).lower():
            flash(
                'At least one etcd connection must remain. '
                'Create another connection before deleting this one.',
                'warning',
            )
        else:
            flash('Could not delete connection. Please retry.', 'danger')

    return redirect(url_for('common.settings_connections'))


@bp.route('/settings/connections/edit/<int:conn_id>', methods=['POST'])
@login_required
def settings_connections_edit(conn_id):
    """Update name, URL, and description of an existing connection profile."""
    name = request.form.get('name', '').strip()
    url  = request.form.get('url', '').strip()
    desc = request.form.get('description', '').strip()

    if not name:
        flash('Connection name is required.', 'danger')
    else:
        valid, message = _validate_etcd_url(url)
        if not valid:
            flash(message, 'danger')
        else:
            try:
                _auth_db.update_connection(conn_id, name, url, desc)
                active = _auth_db.get_active_connection()
                if active and active['id'] == conn_id:
                    state._reinit_etcd(url)
                flash(f'Connection "{name}" updated.', 'success')
            except Exception:
                flash('Could not update connection. Please retry.', 'danger')

    return redirect(url_for('common.settings_connections'))
