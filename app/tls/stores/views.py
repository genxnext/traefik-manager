"""app/tls/stores/views.py — TLS Store CRUD views."""
from flask import render_template, request, redirect, url_for, flash

from app.tls import bp
from app import globals as state
from app.utils import login_required, _parse_csv
from core.models import TLSStore


@bp.route('/tls/stores')
@login_required
def list_tls_stores():
    """List all TLS stores."""
    cm = state.config_manager
    try:
        names  = cm.list_tls_stores()
        stores = [cm.get_tls_store(n) or TLSStore(name=n) for n in names]
        return render_template('tls/stores/index.html', stores=stores)
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
        return render_template('tls/stores/index.html', stores=[])


@bp.route('/tls/stores/create', methods=['GET', 'POST'])
@login_required
def create_tls_store():
    """Create a new TLS store."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required.', 'danger')
            return render_template('tls/stores/create.html', form_data=request.form)
        try:
            store = TLSStore(
                name=name,
                default_certificate_cert=request.form.get('cert_file', '').strip(),
                default_certificate_key=request.form.get('key_file', '').strip(),
                default_generated_cert_resolver=request.form.get('gen_resolver', '').strip(),
                default_generated_cert_domain_main=request.form.get('gen_domain_main', '').strip(),
                default_generated_cert_domain_sans=_parse_csv(request.form.get('gen_domain_sans', '')),
            )
            state.config_manager.create_tls_store(store)
            flash(f'TLS Store "{name}" created!', 'success')
            return redirect(url_for('tls.list_tls_stores'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('tls/stores/create.html', form_data=request.form)

    return render_template('tls/stores/create.html', form_data={})


@bp.route('/tls/stores/delete/<name>', methods=['POST'])
@login_required
def delete_tls_store(name):
    """Delete a TLS store."""
    try:
        state.config_manager.delete_tls_store(name)
        flash(f'TLS Store "{name}" deleted.', 'success')
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
    return redirect(url_for('tls.list_tls_stores'))


@bp.route('/tls/stores/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_tls_store(name):
    """Edit an existing TLS store."""
    cm       = state.config_manager
    existing = cm.get_tls_store(name)
    if not existing:
        flash(f'TLS Store "{name}" not found.', 'warning')
        return redirect(url_for('tls.list_tls_stores'))

    if request.method == 'POST':
        try:
            store = TLSStore(
                name=name,
                default_certificate_cert=request.form.get('cert_file', '').strip(),
                default_certificate_key=request.form.get('key_file', '').strip(),
                default_generated_cert_resolver=request.form.get('gen_resolver', '').strip(),
                default_generated_cert_domain_main=request.form.get('gen_domain_main', '').strip(),
                default_generated_cert_domain_sans=_parse_csv(request.form.get('gen_domain_sans', '')),
            )
            cm.update_tls_store(store)
            flash(f'TLS Store "{name}" updated!', 'success')
            return redirect(url_for('tls.list_tls_stores'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('tls/stores/edit.html', store_name=name, form_data=request.form)

    form_data = {
        'cert_file':       existing.default_certificate_cert,
        'key_file':        existing.default_certificate_key,
        'gen_resolver':    existing.default_generated_cert_resolver,
        'gen_domain_main': existing.default_generated_cert_domain_main,
        'gen_domain_sans': ', '.join(existing.default_generated_cert_domain_sans),
    }
    return render_template('tls/stores/edit.html', store_name=name, form_data=form_data)
