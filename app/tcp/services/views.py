"""app/tcp/services/views.py — TCP Service CRUD views."""
from flask import render_template, request, redirect, url_for, flash

from app.tcp import bp
from app import globals as state
from app.utils import login_required, _parse_csv
from core.models import TCPServer, TCPService


@bp.route('/tcp/services')
@login_required
def list_tcp_services():
    """List all TCP services."""
    try:
        names = state.config_manager.list_tcp_services()
        return render_template('tcp/services/index.html', services=names)
    except Exception as exc:
        flash(f'Error loading TCP services: {str(exc)}', 'danger')
        return render_template('tcp/services/index.html', services=[])


@bp.route('/tcp/services/create', methods=['GET', 'POST'])
@login_required
def create_tcp_service():
    """Create a new TCP service."""
    if request.method == 'POST':
        name      = request.form.get('name', '').strip()
        addresses = _parse_csv(request.form.get('addresses', ''))
        if not name or not addresses:
            flash('Name and at least one server address are required.', 'danger')
            return render_template('tcp/services/create.html', form_data=request.form)
        try:
            service = TCPService(name=name, servers=[TCPServer(address=a) for a in addresses])
            state.config_manager.create_tcp_service(service)
            flash(f'TCP Service "{name}" created!', 'success')
            return redirect(url_for('tcp.list_tcp_services'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('tcp/services/create.html', form_data=request.form)

    return render_template('tcp/services/create.html', form_data={})


@bp.route('/tcp/services/delete/<name>', methods=['POST'])
@login_required
def delete_tcp_service(name):
    """Delete a TCP service — blocked if referenced by any TCP router."""
    cm = state.config_manager
    try:
        in_use = []
        for rname in cm.list_tcp_routers():
            r   = cm.get_tcp_router(rname)
            svc = r.service if hasattr(r, 'service') else (r.get('service', '') if isinstance(r, dict) else '')
            if svc == name:
                in_use.append(rname)
        if in_use:
            flash(
                f'Cannot delete: TCP service "{name}" is in use by TCP router(s): {", ".join(in_use)}',
                'danger',
            )
            return redirect(url_for('tcp.list_tcp_services'))
        cm.delete_tcp_service(name)
        flash(f'TCP Service "{name}" deleted.', 'success')
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
    return redirect(url_for('tcp.list_tcp_services'))


@bp.route('/tcp/services/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_tcp_service(name):
    """Edit an existing TCP service."""
    cm       = state.config_manager
    existing = cm.get_tcp_service(name)
    if not existing:
        flash(f'TCP Service "{name}" not found.', 'warning')
        return redirect(url_for('tcp.list_tcp_services'))

    if request.method == 'POST':
        addresses = _parse_csv(request.form.get('addresses', ''))
        if not addresses:
            flash('At least one server address is required.', 'danger')
            return render_template('tcp/services/edit.html', service_name=name, form_data=request.form)
        try:
            service = TCPService(name=name, servers=[TCPServer(address=a) for a in addresses])
            cm.update_tcp_service(service)
            flash(f'TCP Service "{name}" updated!', 'success')
            return redirect(url_for('tcp.list_tcp_services'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('tcp/services/edit.html', service_name=name, form_data=request.form)

    addresses_str = ', '.join(s.address for s in existing.servers) if existing.servers else ''
    return render_template('tcp/services/edit.html', service_name=name, form_data={'addresses': addresses_str})
