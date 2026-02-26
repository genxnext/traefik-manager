"""app/tls/options/views.py — TLS Options CRUD views."""
from flask import render_template, request, redirect, url_for, flash

from app.tls import bp
from app import globals as state
from app.utils import login_required, _parse_csv
from core.models import TLSOptions


@bp.route('/tls/options')
@login_required
def list_tls_options():
    """List all TLS option sets."""
    cm = state.config_manager
    try:
        names        = cm.list_tls_options()
        options_list = [cm.get_tls_options(n) or TLSOptions(name=n) for n in names]
        return render_template('tls/options/index.html', options_list=options_list)
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
        return render_template('tls/options/index.html', options_list=[])


@bp.route('/tls/options/create', methods=['GET', 'POST'])
@login_required
def create_tls_options():
    """Create a new TLS options profile."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required.', 'danger')
            return render_template('tls/options/create.html', form_data=request.form)
        try:
            opts = TLSOptions(
                name=name,
                min_version=request.form.get('min_version', '').strip(),
                max_version=request.form.get('max_version', '').strip(),
                cipher_suites=_parse_csv(request.form.get('cipher_suites', '')),
                curve_preferences=_parse_csv(request.form.get('curve_preferences', '')),
                sni_strict=request.form.get('sni_strict') == 'on',
                alpn_protocols=_parse_csv(request.form.get('alpn_protocols', '')),
                client_auth_type=request.form.get('client_auth_type', '').strip(),
                client_auth_ca_files=_parse_csv(request.form.get('client_auth_ca_files', '')),
            )
            state.config_manager.create_tls_options(opts)
            flash(f'TLS Options "{name}" created!', 'success')
            return redirect(url_for('tls.list_tls_options'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('tls/options/create.html', form_data=request.form)

    return render_template('tls/options/create.html', form_data={})


@bp.route('/tls/options/delete/<name>', methods=['POST'])
@login_required
def delete_tls_options(name):
    """Delete a TLS options profile."""
    try:
        state.config_manager.delete_tls_options(name)
        flash(f'TLS Options "{name}" deleted.', 'success')
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
    return redirect(url_for('tls.list_tls_options'))


@bp.route('/tls/options/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_tls_options(name):
    """Edit an existing TLS options profile."""
    cm       = state.config_manager
    existing = cm.get_tls_options(name)
    if not existing:
        flash(f'TLS Options "{name}" not found.', 'warning')
        return redirect(url_for('tls.list_tls_options'))

    if request.method == 'POST':
        try:
            opts = TLSOptions(
                name=name,
                min_version=request.form.get('min_version', '').strip(),
                max_version=request.form.get('max_version', '').strip(),
                cipher_suites=_parse_csv(request.form.get('cipher_suites', '')),
                curve_preferences=_parse_csv(request.form.get('curve_preferences', '')),
                sni_strict=request.form.get('sni_strict') == 'on',
                alpn_protocols=_parse_csv(request.form.get('alpn_protocols', '')),
                client_auth_type=request.form.get('client_auth_type', '').strip(),
                client_auth_ca_files=_parse_csv(request.form.get('client_auth_ca_files', '')),
            )
            cm.update_tls_options(opts)
            flash(f'TLS Options "{name}" updated!', 'success')
            return redirect(url_for('tls.list_tls_options'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('tls/options/edit.html', opts_name=name, form_data=request.form)

    form_data = {
        'min_version':          existing.min_version,
        'max_version':          existing.max_version,
        'cipher_suites':        ', '.join(existing.cipher_suites),
        'curve_preferences':    ', '.join(existing.curve_preferences),
        'sni_strict':           existing.sni_strict,
        'alpn_protocols':       ', '.join(existing.alpn_protocols),
        'client_auth_type':     existing.client_auth_type,
        'client_auth_ca_files': ', '.join(existing.client_auth_ca_files),
    }
    return render_template('tls/options/edit.html', opts_name=name, form_data=form_data)
