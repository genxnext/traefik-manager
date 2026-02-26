"""app/http/domains/views.py — HTTP Domain routes."""

from flask import render_template, request, redirect, url_for, flash

from app.http import bp
from app import globals as state
from app.utils import login_required, _parse_csv
from core.models import Domain


# ─── Domains ──────────────────────────────────────────────────────────────────

@bp.route('/domains')
@login_required
def list_domains():
    """List all configured domains."""
    try:
        domains = state.config_manager.get_domains()
        return render_template('http/domains/index.html', domains=domains)
    except Exception as exc:
        flash(f'Error loading domains: {str(exc)}', 'danger')
        return render_template('http/domains/index.html', domains=[])


@bp.route('/domains/create', methods=['GET', 'POST'])
@login_required
def create_domain():
    """Create a new domain registry entry."""
    if request.method == 'POST':
        name          = request.form.get('name', '').strip()
        cert_resolver = request.form.get('cert_resolver', '').strip()
        set_default   = request.form.get('set_default') == 'on'
        sans          = _parse_csv(request.form.get('sans', '').strip())

        if not name:
            flash('Domain name is required.', 'danger')
            return render_template('http/domains/create.html', form_data=request.form)
        if not cert_resolver:
            flash('Certificate resolver is required.', 'danger')
            return render_template('http/domains/create.html', form_data=request.form)

        try:
            domain = Domain(name=name, cert_resolver=cert_resolver, sans=sans)
            if state.config_manager.add_domain(domain, set_as_default=set_default):
                flash(f'Domain "{name}" created successfully!', 'success')
                return redirect(url_for('http.list_domains'))
            flash(f'Failed to create domain "{name}". It may already exist.', 'danger')
        except Exception as exc:
            flash(f'Error creating domain: {str(exc)}', 'danger')
        return render_template('http/domains/create.html', form_data=request.form)

    return render_template('http/domains/create.html', form_data={})


@bp.route('/domains/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_domain(name):
    """Edit an existing domain's cert resolver and SANs."""
    domains = state.config_manager.get_domains()
    domain = next((d for d in domains if d.name == name), None)
    if not domain:
        flash(f'Domain "{name}" not found.', 'warning')
        return redirect(url_for('http.list_domains'))

    if request.method == 'POST':
        cert_resolver = request.form.get('cert_resolver', '').strip()
        sans          = _parse_csv(request.form.get('sans', '').strip())
        if not cert_resolver:
            flash('Certificate resolver is required.', 'danger')
            return render_template('http/domains/edit.html', domain=domain, form_data=request.form)
        try:
            if state.config_manager.update_domain(name, cert_resolver=cert_resolver, sans=sans):
                flash(f'Domain "{name}" updated successfully!', 'success')
                return redirect(url_for('http.list_domains'))
            flash(f'Failed to update domain "{name}".', 'danger')
        except Exception as exc:
            flash(f'Error updating domain: {str(exc)}', 'danger')
        return render_template('http/domains/edit.html', domain=domain, form_data=request.form)

    form_data = {'cert_resolver': domain.cert_resolver, 'sans': ', '.join(domain.sans or [])}
    return render_template('http/domains/edit.html', domain=domain, form_data=form_data)


@bp.route('/domains/delete/<name>', methods=['POST'])
@login_required
def delete_domain(name):
    """Delete a domain from the global config registry."""
    try:
        if state.config_manager.remove_domain(name):
            flash(f'Domain "{name}" deleted successfully!', 'success')
        else:
            flash(f'Cannot delete domain "{name}". Ensure at least one domain remains.', 'warning')
    except Exception as exc:
        flash(f'Error deleting domain: {str(exc)}', 'danger')
    return redirect(url_for('http.list_domains'))


@bp.route('/domains/default/<name>', methods=['POST'])
@login_required
def set_default_domain(name):
    """Mark a domain as the default."""
    try:
        if state.config_manager.set_default_domain(name):
            flash(f'Domain "{name}" set as default.', 'success')
        else:
            flash(f'Failed to set domain "{name}" as default.', 'danger')
    except Exception as exc:
        flash(f'Error setting default domain: {str(exc)}', 'danger')
    return redirect(url_for('http.list_domains'))
