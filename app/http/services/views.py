"""app/http/services/views.py — HTTP Service routes."""

from flask import render_template, request, redirect, url_for, flash

from app.http import bp
from app import globals as state
from app.utils import login_required


# ─── HTTP Services ─────────────────────────────────────────────────────────────

@bp.route('/services')
@login_required
def list_services():
    """List all HTTP services with their primary backend URL."""
    cm = state.config_manager
    ec = state.etcd_client
    try:
        services = cm.list_services()
        service_urls = {
            svc: ec.get(f'traefik/http/services/{svc}/loadbalancer/servers/0/url') or ''
            for svc in services
        }
        return render_template('http/services/index.html', services=services, service_urls=service_urls)
    except Exception as exc:
        flash(f'Error loading services: {str(exc)}', 'danger')
        return render_template('http/services/index.html', services=[], service_urls={})


@bp.route('/services/<name>')
@login_required
def service_detail(name):
    """Show raw etcd KV pairs and the parsed primary URL for a service."""
    ec = state.etcd_client
    prefix = f'traefik/http/services/{name}/'
    try:
        raw_kvs = ec.get_prefix(prefix)
        parsed_primary_url = raw_kvs.get(f'{prefix}loadbalancer/servers/0/url', '')
        if not raw_kvs:
            flash(f'Service "{name}" not found.', 'warning')
        return render_template(
            'http/services/detail.html',
            service_name=name,
            raw_kvs=sorted(raw_kvs.items()),
            parsed_primary_url=parsed_primary_url,
        )
    except Exception as exc:
        flash(f'Error loading service detail: {str(exc)}', 'danger')
        return render_template('http/services/detail.html', service_name=name, raw_kvs=[], parsed_primary_url='')


@bp.route('/services/create', methods=['GET', 'POST'])
@login_required
def create_service():
    """Create a new HTTP loadbalancer service."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        url  = request.form.get('url', '').strip()

        if not name:
            flash('Service name is required.', 'danger')
            return render_template('http/services/create.html', form_data=request.form)
        if not url:
            flash('Backend URL is required.', 'danger')
            return render_template('http/services/create.html', form_data=request.form)

        try:
            if state.config_manager.create_simple_service(name, url):
                flash(f'Service "{name}" created successfully!', 'success')
                return redirect(url_for('http.list_services'))
            flash(f'Failed to create service "{name}".', 'danger')
        except Exception as exc:
            flash(f'Error creating service: {str(exc)}', 'danger')
        return render_template('http/services/create.html', form_data=request.form)

    return render_template('http/services/create.html', form_data={})


@bp.route('/services/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_service(name):
    """Edit the backend URL of an existing simple loadbalancer service."""
    ec = state.etcd_client
    key = f'traefik/http/services/{name}/loadbalancer/servers/0/url'

    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        if not url:
            flash('Backend URL is required.', 'danger')
            return render_template('http/services/edit.html', service_name=name, form_data=request.form)
        try:
            if state.config_manager.create_simple_service(name, url):
                flash(f'Service "{name}" updated successfully!', 'success')
                return redirect(url_for('http.list_services'))
            flash(f'Failed to update service "{name}".', 'danger')
        except Exception as exc:
            flash(f'Error updating service: {str(exc)}', 'danger')
        return render_template('http/services/edit.html', service_name=name, form_data=request.form)

    existing_url = ec.get(key)
    if not existing_url:
        flash(f'Service "{name}" not found or has no simple URL configured.', 'warning')
        return redirect(url_for('http.list_services'))
    return render_template('http/services/edit.html', service_name=name, form_data={'url': existing_url})


@bp.route('/services/delete/<name>', methods=['POST'])
@login_required
def delete_service(name):
    """Delete an HTTP service, blocked if referenced by a router."""
    cm = state.config_manager
    try:
        routers = cm.list_routers()
        in_use = [r.name for r in routers if r.service == name]
        if in_use:
            flash(f'Cannot delete service "{name}". Used by router(s): {", ".join(in_use)}', 'warning')
            return redirect(url_for('http.list_services'))
        if cm.delete_service(name):
            flash(f'Service "{name}" deleted successfully!', 'success')
        else:
            flash(f'Failed to delete service "{name}".', 'danger')
    except Exception as exc:
        flash(f'Error deleting service: {str(exc)}', 'danger')
    return redirect(url_for('http.list_services'))
