"""app/tcp/routers/views.py — TCP Router CRUD views."""
from flask import render_template, request, redirect, url_for, flash

from app.tcp import bp
from app import globals as state
from app.utils import (
    login_required, _normalize_multi, _parse_int,
    _validate_allowed_values, _available_cert_resolvers,
    _tls_cert_resolver_value, _build_tls_config,
)
from core.config_manager import ValidationError
from core.models import TCPRouter, TLSConfig


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tcp_router_form_ctx():
    """Return common template context variables for TCP router forms."""
    cm = state.config_manager
    try:
        tcp_services    = cm.list_tcp_services()
        tcp_middlewares = cm.list_tcp_middlewares()
        tls_options     = cm.list_tls_options()
    except Exception:
        tcp_services    = []
        tcp_middlewares = []
        tls_options     = []
    return {
        'tcp_services':       tcp_services,
        'tcp_middlewares':    tcp_middlewares,
        'tls_options':        tls_options,
        'cert_resolvers':     _available_cert_resolvers(),
        'entrypoint_options': state.TCP_ENTRYPOINT_OPTIONS,
    }


def _render_tcp_router_create(form_data, selected_ep, selected_mw, ctx):
    return render_template(
        'tcp/routers/create.html',
        form_data=form_data,
        selected_entrypoints=selected_ep,
        selected_middlewares=selected_mw,
        **ctx,
    )


def _render_tcp_router_edit(router, form_data, selected_ep, selected_mw, ctx):
    return render_template(
        'tcp/routers/edit.html',
        router=router,
        form_data=form_data,
        selected_entrypoints=selected_ep,
        selected_middlewares=selected_mw,
        **ctx,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@bp.route('/tcp/routers')
@login_required
def list_tcp_routers():
    """List all TCP routers."""
    cm = state.config_manager
    try:
        names   = cm.list_tcp_routers()
        routers = [cm.get_tcp_router(n) or {'name': n} for n in names]
        return render_template('tcp/routers/index.html', routers=routers)
    except Exception as exc:
        flash(f'Error loading TCP routers: {str(exc)}', 'danger')
        return render_template('tcp/routers/index.html', routers=[])


@bp.route('/tcp/routers/create', methods=['GET', 'POST'])
@login_required
def create_tcp_router():
    """Create a new TCP router."""
    ctx = _tcp_router_form_ctx()

    if request.method == 'GET':
        return _render_tcp_router_create({}, ['tcp'], [], ctx)

    # ── POST ─────────────────────────────────────────────────────────────────
    name              = request.form.get('name', '').strip()
    rule              = request.form.get('rule', '').strip() or 'HostSNI(`*`)'
    service           = request.form.get('service', '').strip()
    entrypoints       = _normalize_multi(request.form.getlist('entrypoints'))
    middlewares       = _normalize_multi(request.form.getlist('middlewares'))
    enable_tls        = request.form.get('enable_tls') == 'on'
    tls_passthrough   = request.form.get('tls_passthrough') == 'on'
    cert_resolver     = request.form.get('cert_resolver', '').strip()
    tls_options_value = request.form.get('tls_options', '').strip()
    priority          = _parse_int(request.form.get('priority', '0'))

    def _re_render(msg):
        flash(msg, 'danger')
        return _render_tcp_router_create(request.form, entrypoints, middlewares, ctx)

    if not name or not service:
        return _re_render('Name and service are required.')
    if not ctx['tcp_services']:
        return _re_render('Create at least one TCP service before creating a TCP router.')
    if service not in ctx['tcp_services']:
        return _re_render('Select a valid TCP service from the available options.')
    if not entrypoints:
        return _re_render('Select at least one TCP entrypoint.')

    try:
        _validate_allowed_values(entrypoints, [o['value'] for o in state.TCP_ENTRYPOINT_OPTIONS], 'TCP entrypoints')
        _validate_allowed_values(middlewares, ctx['tcp_middlewares'], 'TCP middlewares')
        if (enable_tls or tls_passthrough) and cert_resolver and cert_resolver not in ctx['cert_resolvers']:
            raise ValidationError('Select a valid TLS certificate resolver.')
        if tls_options_value and tls_options_value not in ctx['tls_options']:
            raise ValidationError('Select a valid TLS options profile.')
    except ValidationError as exc:
        return _re_render(str(exc))

    try:
        tls = _build_tls_config(enable_tls or tls_passthrough, cert_resolver, tls_options_value, tls_passthrough)
        router = TCPRouter(
            name=name, rule=rule, service=service,
            entrypoints=entrypoints, middlewares=middlewares,
            tls=tls, tls_passthrough=tls_passthrough, priority=priority,
        )
        state.config_manager.create_tcp_router(router)
        flash(f'TCP Router "{name}" created!', 'success')
        return redirect(url_for('tcp.list_tcp_routers'))
    except Exception as exc:
        return _re_render(f'Error: {str(exc)}')


@bp.route('/tcp/routers/delete/<name>', methods=['POST'])
@login_required
def delete_tcp_router(name):
    """Delete a TCP router."""
    try:
        state.config_manager.delete_tcp_router(name)
        flash(f'TCP Router "{name}" deleted.', 'success')
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
    return redirect(url_for('tcp.list_tcp_routers'))


@bp.route('/tcp/routers/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_tcp_router(name):
    """Edit an existing TCP router."""
    cm  = state.config_manager
    ctx = _tcp_router_form_ctx()

    existing = cm.get_tcp_router(name)
    if not existing:
        flash(f'TCP Router "{name}" not found.', 'warning')
        return redirect(url_for('tcp.list_tcp_routers'))

    if request.method == 'GET':
        form_data = {
            'rule':            existing.rule,
            'service':         existing.service,
            'entrypoints':     existing.entrypoints,
            'middlewares':     existing.middlewares,
            'enable_tls':      bool(existing.tls),
            'cert_resolver':   _tls_cert_resolver_value(existing.tls) if existing.tls else '',
            'tls_options':     existing.tls.options if existing.tls else '',
            'priority':        existing.priority,
            'tls_passthrough': existing.tls_passthrough,
        }
        return _render_tcp_router_edit(existing, form_data, existing.entrypoints, existing.middlewares, ctx)

    # ── POST ─────────────────────────────────────────────────────────────────
    rule              = request.form.get('rule', '').strip() or 'HostSNI(`*`)'
    service           = request.form.get('service', '').strip()
    entrypoints       = _normalize_multi(request.form.getlist('entrypoints'))
    middlewares       = _normalize_multi(request.form.getlist('middlewares'))
    enable_tls        = request.form.get('enable_tls') == 'on'
    tls_passthrough   = request.form.get('tls_passthrough') == 'on'
    cert_resolver     = request.form.get('cert_resolver', '').strip()
    tls_options_value = request.form.get('tls_options', '').strip()
    priority          = _parse_int(request.form.get('priority', '0'))

    def _re_render(msg):
        flash(msg, 'danger')
        return _render_tcp_router_edit(existing, request.form, entrypoints, middlewares, ctx)

    if not service:
        return _re_render('Service is required.')
    if service not in ctx['tcp_services']:
        return _re_render('Select a valid TCP service from the available options.')
    if not entrypoints:
        return _re_render('Select at least one TCP entrypoint.')

    try:
        _validate_allowed_values(entrypoints, [o['value'] for o in state.TCP_ENTRYPOINT_OPTIONS], 'TCP entrypoints')
        _validate_allowed_values(middlewares, ctx['tcp_middlewares'], 'TCP middlewares')
        if (enable_tls or tls_passthrough) and cert_resolver and cert_resolver not in ctx['cert_resolvers']:
            raise ValidationError('Select a valid TLS certificate resolver.')
        if tls_options_value and tls_options_value not in ctx['tls_options']:
            raise ValidationError('Select a valid TLS options profile.')
    except ValidationError as exc:
        return _re_render(str(exc))

    try:
        tls = _build_tls_config(enable_tls or tls_passthrough, cert_resolver, tls_options_value, tls_passthrough)
        router = TCPRouter(
            name=name, rule=rule, service=service,
            entrypoints=entrypoints, middlewares=middlewares,
            tls=tls, tls_passthrough=tls_passthrough, priority=priority,
        )
        cm.update_tcp_router(router)
        flash(f'TCP Router "{name}" updated!', 'success')
        return redirect(url_for('tcp.list_tcp_routers'))
    except Exception as exc:
        return _re_render(f'Error: {str(exc)}')
