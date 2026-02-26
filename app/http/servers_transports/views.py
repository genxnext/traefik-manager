"""app/http/servers_transports/views.py — HTTP ServersTransport routes."""

from flask import render_template, request, redirect, url_for, flash

from app.http import bp
from app import globals as state
from app.utils import login_required, _parse_int, _parse_csv
from core.models import ServersTransport


# ─── ServersTransport ─────────────────────────────────────────────────────────

@bp.route('/serversTransports')
@login_required
def list_servers_transports():
    """List all HTTP ServersTransport entries."""
    cm = state.config_manager
    try:
        names = cm.list_servers_transports()
        transports = [cm.get_servers_transport(n) or ServersTransport(name=n) for n in names]
        return render_template('http/transports/index.html', transports=transports)
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
        return render_template('http/transports/index.html', transports=[])


@bp.route('/serversTransports/create', methods=['GET', 'POST'])
@login_required
def create_servers_transport():
    """Create a new HTTP ServersTransport entry."""
    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        if not name:
            flash('Name is required.', 'danger')
            return render_template('http/transports/create.html', form_data=request.form)
        try:
            transport = ServersTransport(
                name=name,
                server_name=request.form.get('server_name', '').strip(),
                insecure_skip_verify=request.form.get('insecure_skip_verify') == 'on',
                root_cas=_parse_csv(request.form.get('root_cas', '')),
                max_idle_conns_per_host=_parse_int(request.form.get('max_idle_conns', ''), 0),
                disable_http2=request.form.get('disable_http2') == 'on',
                peer_cert_uri=request.form.get('peer_cert_uri', '').strip(),
            )
            state.config_manager.create_servers_transport(transport)
            flash(f'ServersTransport "{name}" created!', 'success')
            return redirect(url_for('http.list_servers_transports'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('http/transports/create.html', form_data=request.form)

    return render_template('http/transports/create.html', form_data={})


@bp.route('/serversTransports/delete/<name>', methods=['POST'])
@login_required
def delete_servers_transport(name):
    """Delete an HTTP ServersTransport entry."""
    try:
        state.config_manager.delete_servers_transport(name)
        flash(f'ServersTransport "{name}" deleted.', 'success')
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
    return redirect(url_for('http.list_servers_transports'))


@bp.route('/serversTransports/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_servers_transport(name):
    """Edit an existing HTTP ServersTransport entry."""
    cm = state.config_manager
    existing = cm.get_servers_transport(name)
    if not existing:
        flash(f'ServersTransport "{name}" not found.', 'warning')
        return redirect(url_for('http.list_servers_transports'))

    if request.method == 'POST':
        try:
            transport = ServersTransport(
                name=name,
                server_name=request.form.get('server_name', '').strip(),
                insecure_skip_verify=request.form.get('insecure_skip_verify') == 'on',
                root_cas=_parse_csv(request.form.get('root_cas', '')),
                max_idle_conns_per_host=_parse_int(request.form.get('max_idle_conns', ''), 0),
                disable_http2=request.form.get('disable_http2') == 'on',
                peer_cert_uri=request.form.get('peer_cert_uri', '').strip(),
            )
            cm.update_servers_transport(transport)
            flash(f'ServersTransport "{name}" updated!', 'success')
            return redirect(url_for('http.list_servers_transports'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('http/transports/edit.html', transport_name=name, form_data=request.form)

    form_data = {
        'server_name':         existing.server_name,
        'insecure_skip_verify':existing.insecure_skip_verify,
        'root_cas':            ', '.join(existing.root_cas),
        'max_idle_conns':      existing.max_idle_conns_per_host,
        'disable_http2':       existing.disable_http2,
        'peer_cert_uri':       existing.peer_cert_uri,
    }
    return render_template('http/transports/edit.html', transport_name=name, form_data=form_data)
