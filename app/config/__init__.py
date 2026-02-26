"""
app/config_routes.py — Config Blueprint.

Covers: Export (download, full backup), Import (routers/services, full backup)
"""

import json
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    make_response,
)

import auth_db as _auth_db
from app import globals as state
from app.utils import login_required, _json_default_serializer

bp = Blueprint('config', __name__, template_folder='templates')


# ─── Export ────────────────────────────────────────────────────────────────────

@bp.route('/config/export')
@login_required
def export_config():
    """Show the export options page."""
    return render_template('config/export.html')


@bp.route('/config/export/download')
@login_required
def export_config_download():
    """Download Traefik config as a JSON file."""
    try:
        exported = state.config_manager.export_full_config()
        payload = json.dumps(exported, indent=2, default=_json_default_serializer)
        response = make_response(payload)
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = 'attachment; filename=traefik-config-export.json'
        return response
    except Exception as exc:
        flash(f'Error exporting config: {str(exc)}', 'danger')
        return redirect(url_for('config.export_config'))


@bp.route('/config/export/backup')
@login_required
def export_full_backup():
    """Download a full backup: all etcd KVs under traefik/ plus connection profiles."""
    try:
        # Query both possible prefixes (with and without leading slash) to ensure we get all keys
        all_kvs = {}
        all_kvs.update(state.etcd_client.get_prefix('traefik/'))      # Main prefix (without leading slash)
        all_kvs.update(state.etcd_client.get_prefix('/traefik/'))     # Alternative (with leading slash)
        
        conns   = _auth_db.list_connections()

        backup = {
            'version':     '1.0',
            'exported_at': datetime.utcnow().isoformat() + 'Z',
            'etcd_prefix': 'traefik/',
            'etcd_kvs':    all_kvs,
            'connections': [
                {
                    'name':        c['name'],
                    'url':         c['url'],
                    'description': c.get('description', ''),
                }
                for c in conns
            ],
        }

        ts = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        response = make_response(json.dumps(backup, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=traefik-backup-{ts}.json'
        return response
    except Exception as exc:
        flash(f'Backup export failed: {str(exc)}', 'danger')
        return redirect(url_for('config.export_config'))


# ─── Import ────────────────────────────────────────────────────────────────────

@bp.route('/config/import/backup', methods=['POST'])
@login_required
def import_full_backup():
    """Restore a full backup: write etcd KVs and optionally add connection profiles."""
    backup_file = request.files.get('backup_file')
    if not backup_file or not backup_file.filename:
        flash('No backup file selected.', 'danger')
        return redirect(url_for('config.import_config'))

    try:
        raw    = backup_file.read().decode('utf-8')
        backup = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        flash(f'Invalid backup file: {str(exc)}', 'danger')
        return redirect(url_for('config.import_config'))

    if not isinstance(backup, dict) or 'etcd_kvs' not in backup:
        flash('File does not look like a Traefik Manager backup (missing etcd_kvs key).', 'danger')
        return redirect(url_for('config.import_config'))

    try:
        kv_ok = kv_fail = 0
        for key, value in backup.get('etcd_kvs', {}).items():
            try:
                if state.etcd_client.put(str(key), str(value)):
                    kv_ok += 1
                else:
                    kv_fail += 1
            except Exception:
                kv_fail += 1

        conn_ok = conn_skip = 0
        if request.form.get('import_connections') == 'on':
            existing_urls = {c['url'] for c in _auth_db.list_connections()}
            for conn in backup.get('connections', []):
                url  = (conn.get('url') or '').strip()
                name = (conn.get('name') or url).strip()
                if url and url not in existing_urls:
                    try:
                        _auth_db.add_connection(name, url, conn.get('description', ''))
                        conn_ok += 1
                    except Exception:
                        pass
                else:
                    conn_skip += 1

        cat   = 'success' if kv_fail == 0 else 'warning'
        parts = [f'{kv_ok} etcd key(s) restored']
        if kv_fail:
            parts.append(f'{kv_fail} failed')
        if request.form.get('import_connections') == 'on':
            parts.append(f'{conn_ok} connection(s) added, {conn_skip} skipped')
        flash('Backup import complete — ' + ', '.join(parts) + '.', cat)
        return redirect(url_for('common.index'))

    except Exception as exc:
        flash(f'Backup import failed: {str(exc)}', 'danger')
        return redirect(url_for('config.import_config'))


@bp.route('/config/import', methods=['GET', 'POST'])
@login_required
def import_config():
    """Import routers or services from a JSON payload."""
    if request.method == 'GET':
        return render_template('config/import.html', form_data={'merge': 'on', 'import_type': 'routers'})

    config_json = request.form.get('config_json', '').strip()
    merge       = request.form.get('merge') == 'on'
    import_type = request.form.get('import_type', 'routers').strip()

    if not config_json:
        flash('JSON configuration is required.', 'danger')
        return render_template('config/import.html', form_data=request.form)

    try:
        data = json.loads(config_json)
    except json.JSONDecodeError as exc:
        flash(f'Invalid JSON: {str(exc)}', 'danger')
        return render_template('config/import.html', form_data=request.form)

    cm = state.config_manager

    try:
        if import_type == 'routers':
            routers_data = _extract_list(data, 'routers')
            if routers_data is None:
                flash('No routers list found. Expected data["http"]["routers"], data["routers"], or a plain list.', 'danger')
                return render_template('config/import.html', form_data=request.form)

            for idx, item in enumerate(routers_data, start=1):
                if not isinstance(item, dict):
                    flash(f'Invalid router at index {idx}: expected an object/dict.', 'danger')
                    return render_template('config/import.html', form_data=request.form)
                missing = [f for f in ('name', 'rule', 'service') if not item.get(f)]
                if missing:
                    flash(f'Router at index {idx} missing: {", ".join(missing)}.', 'danger')
                    return render_template('config/import.html', form_data=request.form)

            ok, fail = cm.import_routers(routers_data, merge=merge)
            cat = 'success' if fail == 0 else 'warning'
            flash(f'Routers import: {ok} succeeded, {fail} failed (total {len(routers_data)}).', cat)
            return redirect(url_for('http.list_routers'))

        if import_type == 'services':
            services_data = _extract_list(data, 'services')
            if services_data is None:
                flash('No services list found. Provide a list of {"name":..., "url":...} objects.', 'danger')
                return render_template('config/import.html', form_data=request.form)

            ok = fail = 0
            for item in services_data:
                if not isinstance(item, dict):
                    fail += 1
                    continue
                svc_name = item.get('name', '').strip()
                svc_url  = item.get('url', item.get('primary_url', '')).strip()
                if not svc_name or not svc_url:
                    fail += 1
                    continue
                try:
                    cm.create_simple_service(svc_name, svc_url)
                    ok += 1
                except Exception:
                    fail += 1

            cat = 'success' if fail == 0 else 'warning'
            flash(f'Services import: {ok} succeeded, {fail} failed.', cat)
            return redirect(url_for('http.list_services'))

        flash(f'Unknown import type: {import_type}', 'danger')
        return render_template('config/import.html', form_data=request.form)

    except Exception as exc:
        flash(f'Error during import: {str(exc)}', 'danger')
        return render_template('config/import.html', form_data=request.form)


def _extract_list(data, key: str):
    """Extract a list from a nested or flat JSON structure."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get('http'), dict) and isinstance(data['http'].get(key), list):
            return data['http'][key]
        if isinstance(data.get(key), list):
            return data[key]
    return None
