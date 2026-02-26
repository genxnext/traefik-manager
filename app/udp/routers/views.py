"""app/udp/routers/views.py — UDP Router CRUD views."""
from flask import render_template, request, redirect, url_for, flash

from app.udp import bp
from app import globals as state
from app.utils import login_required, _normalize_multi, _validate_allowed_values
from core.config_manager import ValidationError


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _render_udp_router_create(form_data, selected_ep, udp_services):
    return render_template(
        'udp/routers/create.html',
        form_data=form_data,
        udp_services=udp_services,
        entrypoint_options=state.UDP_ENTRYPOINT_OPTIONS,
        selected_entrypoints=selected_ep,
    )


def _render_udp_router_edit(router_name, form_data, selected_ep, udp_services):
    return render_template(
        'udp/routers/edit.html',
        router_name=router_name,
        form_data=form_data,
        udp_services=udp_services,
        entrypoint_options=state.UDP_ENTRYPOINT_OPTIONS,
        selected_entrypoints=selected_ep,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@bp.route('/udp/routers')
@login_required
def list_udp_routers():
    """List all UDP routers."""
    cm = state.config_manager
    try:
        names   = cm.list_udp_routers()
        routers = [cm.get_udp_router(n) or {'name': n} for n in names]
        return render_template('udp/routers/index.html', routers=routers)
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
        return render_template('udp/routers/index.html', routers=[])


@bp.route('/udp/routers/create', methods=['GET', 'POST'])
@login_required
def create_udp_router():
    """Create a new UDP router."""
    cm = state.config_manager
    try:
        udp_services = cm.list_udp_services()
    except Exception:
        udp_services = []

    if request.method == 'GET':
        return _render_udp_router_create({}, ['udp'], udp_services)

    # ── POST ─────────────────────────────────────────────────────────────────
    name        = request.form.get('name', '').strip()
    service     = request.form.get('service', '').strip()
    entrypoints = _normalize_multi(request.form.getlist('entrypoints'))

    def _re_render(msg):
        flash(msg, 'danger')
        return _render_udp_router_create(request.form, entrypoints, udp_services)

    if not name or not service:
        return _re_render('Name and service are required.')
    if not udp_services:
        return _re_render('Create at least one UDP service before creating a UDP router.')
    if service not in udp_services:
        return _re_render('Select a valid UDP service from the available options.')
    if not entrypoints:
        return _re_render('Select at least one UDP entrypoint.')

    try:
        _validate_allowed_values(entrypoints, [o['value'] for o in state.UDP_ENTRYPOINT_OPTIONS], 'UDP entrypoints')
    except ValidationError as exc:
        return _re_render(str(exc))

    try:
        cm.create_udp_router(name, service, entrypoints)
        flash(f'UDP Router "{name}" created!', 'success')
        return redirect(url_for('udp.list_udp_routers'))
    except Exception as exc:
        return _re_render(f'Error: {str(exc)}')


@bp.route('/udp/routers/delete/<name>', methods=['POST'])
@login_required
def delete_udp_router(name):
    """Delete a UDP router."""
    try:
        state.config_manager.delete_udp_router(name)
        flash(f'UDP Router "{name}" deleted.', 'success')
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
    return redirect(url_for('udp.list_udp_routers'))


@bp.route('/udp/routers/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_udp_router(name):
    """Edit an existing UDP router."""
    cm = state.config_manager
    try:
        udp_services = cm.list_udp_services()
    except Exception:
        udp_services = []

    existing = cm.get_udp_router(name)
    if not existing:
        flash(f'UDP Router "{name}" not found.', 'warning')
        return redirect(url_for('udp.list_udp_routers'))

    if request.method == 'GET':
        svc = existing.get('service', '') if isinstance(existing, dict) else getattr(existing, 'service', '')
        eps = existing.get('entrypoints', []) if isinstance(existing, dict) else getattr(existing, 'entrypoints', [])
        return _render_udp_router_edit(name, {'service': svc, 'entrypoints': eps}, eps, udp_services)

    # ── POST ─────────────────────────────────────────────────────────────────
    service     = request.form.get('service', '').strip()
    entrypoints = _normalize_multi(request.form.getlist('entrypoints'))

    def _re_render(msg):
        flash(msg, 'danger')
        return _render_udp_router_edit(name, request.form, entrypoints, udp_services)

    if not service:
        return _re_render('Service is required.')
    if service not in udp_services:
        return _re_render('Select a valid UDP service from the available options.')
    if not entrypoints:
        return _re_render('Select at least one UDP entrypoint.')

    try:
        _validate_allowed_values(entrypoints, [o['value'] for o in state.UDP_ENTRYPOINT_OPTIONS], 'UDP entrypoints')
    except ValidationError as exc:
        return _re_render(str(exc))

    try:
        cm.create_udp_router(name, service, entrypoints)
        flash(f'UDP Router "{name}" updated!', 'success')
        return redirect(url_for('udp.list_udp_routers'))
    except Exception as exc:
        return _re_render(f'Error: {str(exc)}')
