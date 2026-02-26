"""app/http/routers/views.py — HTTP Router routes."""

from flask import render_template, request, redirect, url_for, flash

from app.http import bp
from app import globals as state
from app.utils import (
    login_required,
    _normalize_multi,
    _parse_int,
    _parse_csv,
    _validate_allowed_values,
    _available_cert_resolvers,
    _tls_cert_resolver_value,
    _build_tls_config,
)
from core.config_manager import ValidationError
from core.models import Router, TLSConfig


# ─── Helper: render the router form ───────────────────────────────────────────

def _render_router_form(template: str, form_data: dict, **extra):
    """Render a router create/edit form with all required template variables."""
    cm = state.config_manager
    try:
        services = cm.list_services()
        middlewares = cm.list_middlewares()
        tls_options = cm.list_tls_options()
    except Exception as exc:
        flash(f'Error loading form data: {str(exc)}', 'danger')
        services = []
        middlewares = []
        tls_options = []

    return render_template(
        template,
        services=services,
        middlewares=middlewares,
        tls_options=tls_options,
        cert_resolvers=_available_cert_resolvers(),
        entrypoint_options=state.HTTP_ENTRYPOINT_OPTIONS,
        form_data=form_data,
        **extra,
    )


# ─── HTTP Routers ──────────────────────────────────────────────────────────────

@bp.route('/routers')
@login_required
def list_routers():
    """List all HTTP routers."""
    try:
        routers = state.config_manager.list_routers()
        return render_template('http/routers/index.html', routers=routers)
    except Exception as exc:
        flash(f'Error loading routers: {str(exc)}', 'danger')
        return render_template('http/routers/index.html', routers=[])


@bp.route('/routers/create', methods=['GET', 'POST'])
@login_required
def create_router():
    """Create a new HTTP router."""
    cm = state.config_manager

    if request.method == 'GET':
        return _render_router_form(
            'http/routers/create.html',
            form_data={},
            selected_middlewares=[],
            selected_entrypoints=['websecure'],
        )

    # ── POST ─────────────────────────────────────────────────────────────────
    name               = request.form.get('name', '').strip()
    hostname           = request.form.get('hostname', '').strip()
    rule               = request.form.get('rule', '').strip()
    service            = request.form.get('service', '').strip()
    entrypoints        = _normalize_multi(request.form.getlist('entrypoints'))
    middlewares_sel    = _normalize_multi(request.form.getlist('middlewares'))
    enable_tls         = request.form.get('enable_tls') == 'on'
    cert_resolver      = request.form.get('cert_resolver', 'letsencrypt').strip()
    tls_options_value  = request.form.get('tls_options', '').strip()
    priority           = _parse_int(request.form.get('priority', '0'))

    def _re_render(msg, level='danger'):
        flash(msg, level)
        return _render_router_form(
            'http/routers/create.html',
            form_data=request.form,
            selected_middlewares=middlewares_sel,
            selected_entrypoints=entrypoints,
        )

    try:
        services_avail = cm.list_services()
        middlewares_avail = cm.list_middlewares()
        cert_resolvers_avail = _available_cert_resolvers()

        if not services_avail:
            return _re_render('Create at least one HTTP service before creating a router.')
        if service not in services_avail:
            return _re_render('Select a valid HTTP service from the available options.')
        if not entrypoints:
            return _re_render('Select at least one entrypoint.')

        _validate_allowed_values(entrypoints, [o['value'] for o in state.HTTP_ENTRYPOINT_OPTIONS], 'HTTP entrypoints')
        _validate_allowed_values(middlewares_sel, middlewares_avail, 'HTTP middlewares')

        if not rule and not hostname:
            return _re_render('Provide either a hostname or a rule.')

        effective_rule = rule if rule else f'Host(`{hostname}`)'

        if enable_tls:
            if cert_resolver and cert_resolver not in cert_resolvers_avail:
                return _re_render('Select a valid TLS certificate resolver.')
            tls_opts_avail = cm.list_tls_options()
            if tls_options_value and tls_options_value not in tls_opts_avail:
                return _re_render('Select a valid TLS options profile.')

        tls = _build_tls_config(enable_tls, cert_resolver, tls_options_value)
        router = Router(
            name=name, rule=effective_rule, service=service,
            entrypoints=entrypoints, middlewares=middlewares_sel,
            priority=priority, tls=tls,
        )
        cm.create_router(router)
        flash(f'Router "{name}" created successfully!', 'success')
        return redirect(url_for('http.list_routers'))

    except ValidationError as exc:
        return _re_render(f'Validation error: {str(exc)}')
    except Exception as exc:
        return _re_render(f'Error creating router: {str(exc)}')


@bp.route('/routers/delete/<name>', methods=['POST'])
@login_required
def delete_router(name):
    """Delete an HTTP router by name."""
    try:
        state.config_manager.delete_router(name)
        flash(f'Router "{name}" deleted successfully!', 'success')
    except Exception as exc:
        flash(f'Error deleting router: {str(exc)}', 'danger')
    return redirect(url_for('http.list_routers'))


@bp.route('/routers/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_router(name):
    """Edit an existing HTTP router."""
    cm = state.config_manager

    existing = cm.get_router(name)
    if not existing:
        flash(f'Router "{name}" not found.', 'warning')
        return redirect(url_for('http.list_routers'))

    try:
        services    = cm.list_services()
        middlewares = cm.list_middlewares()
        tls_options = cm.list_tls_options()
    except Exception as exc:
        flash(f'Error loading form data: {str(exc)}', 'danger')
        services = []
        middlewares = []
        tls_options = []

    def _re_render(msg, level='danger', mw_sel=None, ep_sel=None):
        flash(msg, level)
        return render_template(
            'http/routers/edit.html',
            router=existing,
            services=services,
            middlewares=middlewares,
            tls_options=tls_options,
            cert_resolvers=_available_cert_resolvers(),
            entrypoint_options=state.HTTP_ENTRYPOINT_OPTIONS,
            form_data=request.form,
            selected_middlewares=mw_sel or [],
            selected_entrypoints=ep_sel or [],
        )

    if request.method == 'GET':
        form_data = {
            'hostname':      _tls_cert_resolver_value(existing.tls) if existing.tls else '',
            'rule':          existing.rule,
            'service':       existing.service,
            'entrypoints':   existing.entrypoints,
            'enable_tls':    bool(existing.tls),
            'cert_resolver': _tls_cert_resolver_value(existing.tls) if existing.tls else 'letsencrypt',
            'tls_options':   existing.tls.options if existing.tls else '',
            'priority':      existing.priority,
        }
        # The hostname display helper
        from app.utils import _extract_hostname_from_rule
        form_data['hostname'] = _extract_hostname_from_rule(existing.rule)
        return render_template(
            'http/routers/edit.html',
            router=existing,
            services=services,
            middlewares=middlewares,
            tls_options=tls_options,
            cert_resolvers=_available_cert_resolvers(),
            entrypoint_options=state.HTTP_ENTRYPOINT_OPTIONS,
            form_data=form_data,
            selected_middlewares=existing.middlewares,
            selected_entrypoints=existing.entrypoints,
        )

    # ── POST ─────────────────────────────────────────────────────────────────
    hostname          = request.form.get('hostname', '').strip()
    rule              = request.form.get('rule', '').strip()
    service           = request.form.get('service', '').strip()
    entrypoints       = _normalize_multi(request.form.getlist('entrypoints'))
    middlewares_sel   = _normalize_multi(request.form.getlist('middlewares'))
    enable_tls        = request.form.get('enable_tls') == 'on'
    cert_resolver     = request.form.get('cert_resolver', 'letsencrypt').strip()
    tls_options_value = request.form.get('tls_options', '').strip()
    priority          = _parse_int(request.form.get('priority', '0'))

    cert_resolvers_avail = _available_cert_resolvers()

    try:
        if not services:
            return _re_render('Create at least one HTTP service before editing this router.', mw_sel=middlewares_sel, ep_sel=entrypoints)
        if service not in services:
            return _re_render('Select a valid HTTP service from the available options.', mw_sel=middlewares_sel, ep_sel=entrypoints)
        if not hostname and not rule:
            return _re_render('Provide either a hostname or a rule.', mw_sel=middlewares_sel, ep_sel=entrypoints)
        if not entrypoints:
            return _re_render('Select at least one entrypoint.', mw_sel=middlewares_sel, ep_sel=entrypoints)

        _validate_allowed_values(entrypoints, [o['value'] for o in state.HTTP_ENTRYPOINT_OPTIONS], 'HTTP entrypoints')
        _validate_allowed_values(middlewares_sel, middlewares, 'HTTP middlewares')

        effective_rule = rule if rule else f'Host(`{hostname}`)'

        if enable_tls:
            if cert_resolver and cert_resolver not in cert_resolvers_avail:
                return _re_render('Select a valid TLS certificate resolver.', mw_sel=middlewares_sel, ep_sel=entrypoints)
            if tls_options_value and tls_options_value not in tls_options:
                return _re_render('Select a valid TLS options profile.', mw_sel=middlewares_sel, ep_sel=entrypoints)

        tls = _build_tls_config(enable_tls, cert_resolver, tls_options_value)
        router = Router(
            name=name, rule=effective_rule, service=service,
            entrypoints=entrypoints, middlewares=middlewares_sel,
            priority=priority, tls=tls,
        )
        cm.update_router(router)
        flash(f'Router "{name}" updated successfully!', 'success')
        return redirect(url_for('http.list_routers'))

    except ValidationError as exc:
        return _re_render(f'Validation error: {str(exc)}', mw_sel=middlewares_sel, ep_sel=entrypoints)
    except Exception as exc:
        return _re_render(f'Error updating router: {str(exc)}', mw_sel=middlewares_sel, ep_sel=entrypoints)
