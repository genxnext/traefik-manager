"""app/udp/services/views.py — UDP Service CRUD views."""
from flask import render_template, request, redirect, url_for, flash

from app.udp import bp
from app import globals as state
from app.utils import login_required, _parse_csv
from core.models import UDPServer, UDPService


@bp.route('/udp/services')
@login_required
def list_udp_services():
    """List all UDP services."""
    try:
        names = state.config_manager.list_udp_services()
        return render_template('udp/services/index.html', services=names)
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
        return render_template('udp/services/index.html', services=[])


@bp.route('/udp/services/create', methods=['GET', 'POST'])
@login_required
def create_udp_service():
    """Create a new UDP service."""
    if request.method == 'POST':
        name      = request.form.get('name', '').strip()
        addresses = _parse_csv(request.form.get('addresses', ''))
        if not name or not addresses:
            flash('Name and at least one server address are required.', 'danger')
            return render_template('udp/services/create.html', form_data=request.form)
        try:
            service = UDPService(name=name, servers=[UDPServer(address=a) for a in addresses])
            state.config_manager.create_udp_service(service)
            flash(f'UDP Service "{name}" created!', 'success')
            return redirect(url_for('udp.list_udp_services'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('udp/services/create.html', form_data=request.form)

    return render_template('udp/services/create.html', form_data={})


@bp.route('/udp/services/delete/<name>', methods=['POST'])
@login_required
def delete_udp_service(name):
    """Delete a UDP service — blocked if referenced by any UDP router."""
    cm = state.config_manager
    try:
        in_use = []
        for rname in cm.list_udp_routers():
            r   = cm.get_udp_router(rname)
            svc = r.get('service', '') if isinstance(r, dict) else getattr(r, 'service', '')
            if svc == name:
                in_use.append(rname)
        if in_use:
            flash(
                f'Cannot delete: UDP service "{name}" is in use by UDP router(s): {", ".join(in_use)}',
                'danger',
            )
            return redirect(url_for('udp.list_udp_services'))
        cm.delete_udp_service(name)
        flash(f'UDP Service "{name}" deleted.', 'success')
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
    return redirect(url_for('udp.list_udp_services'))


@bp.route('/udp/services/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_udp_service(name):
    """Edit an existing UDP service."""
    cm       = state.config_manager
    existing = cm.get_udp_service(name)
    if not existing:
        flash(f'UDP Service "{name}" not found.', 'warning')
        return redirect(url_for('udp.list_udp_services'))

    if request.method == 'POST':
        addresses = _parse_csv(request.form.get('addresses', ''))
        if not addresses:
            flash('At least one server address is required.', 'danger')
            return render_template('udp/services/edit.html', service_name=name, form_data=request.form)
        try:
            service = UDPService(name=name, servers=[UDPServer(address=a) for a in addresses])
            cm.create_udp_service(service)
            flash(f'UDP Service "{name}" updated!', 'success')
            return redirect(url_for('udp.list_udp_services'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('udp/services/edit.html', service_name=name, form_data=request.form)

    addresses_str = ', '.join(s.address for s in existing.servers) if existing.servers else ''
    return render_template('udp/services/edit.html', service_name=name, form_data={'addresses': addresses_str})
