"""app/tcp/middlewares/views.py — TCP Middleware CRUD views."""
from flask import render_template, request, redirect, url_for, flash

from app.tcp import bp
from app import globals as state
from app.utils import login_required, _parse_int, _parse_csv
from core.models import TCPMiddlewareType


@bp.route('/tcp/middlewares')
@login_required
def list_tcp_middlewares():
    """List all TCP middlewares."""
    try:
        names = state.config_manager.list_tcp_middlewares()
        return render_template('tcp/middlewares/index.html', middlewares=names)
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
        return render_template('tcp/middlewares/index.html', middlewares=[])


@bp.route('/tcp/middlewares/create', methods=['GET', 'POST'])
@login_required
def create_tcp_middleware():
    """Create a TCP middleware (inFlightConn or ipAllowList)."""
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        mw_type = request.form.get('middleware_type', '').strip()
        if not name or not mw_type:
            flash('Name and type are required.', 'danger')
            return render_template('tcp/middlewares/create.html', form_data=request.form)
        try:
            cm = state.config_manager
            if mw_type == TCPMiddlewareType.IN_FLIGHT_CONN.value:
                cm.create_tcp_middleware(
                    name, TCPMiddlewareType.IN_FLIGHT_CONN,
                    {'amount': _parse_int(request.form.get('amount', '10'), 10)},
                )
            elif mw_type == TCPMiddlewareType.IP_ALLOW_LIST.value:
                cm.create_tcp_middleware(
                    name, TCPMiddlewareType.IP_ALLOW_LIST,
                    {'sourceRange': _parse_csv(request.form.get('source_range', ''))},
                )
            else:
                flash('Unknown TCP middleware type.', 'danger')
                return render_template('tcp/middlewares/create.html', form_data=request.form)
            flash(f'TCP Middleware "{name}" created!', 'success')
            return redirect(url_for('tcp.list_tcp_middlewares'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template('tcp/middlewares/create.html', form_data=request.form)

    return render_template('tcp/middlewares/create.html', form_data={})


@bp.route('/tcp/middlewares/delete/<name>', methods=['POST'])
@login_required
def delete_tcp_middleware(name):
    """Delete a TCP middleware — blocked if referenced by any TCP router."""
    cm = state.config_manager
    try:
        in_use = []
        for rname in cm.list_tcp_routers():
            r   = cm.get_tcp_router(rname)
            mws = r.middlewares if hasattr(r, 'middlewares') else (r.get('middlewares', []) if isinstance(r, dict) else [])
            if name in (mws or []):
                in_use.append(rname)
        if in_use:
            flash(
                f'Cannot delete: TCP middleware "{name}" is in use by TCP router(s): {", ".join(in_use)}',
                'danger',
            )
            return redirect(url_for('tcp.list_tcp_middlewares'))
        cm.delete_tcp_middleware(name)
        flash(f'TCP Middleware "{name}" deleted.', 'success')
    except Exception as exc:
        flash(f'Error: {str(exc)}', 'danger')
    return redirect(url_for('tcp.list_tcp_middlewares'))


@bp.route('/tcp/middlewares/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_tcp_middleware(name):
    """Edit an existing TCP middleware."""
    cm       = state.config_manager
    existing = cm.get_tcp_middleware(name)
    if not existing:
        flash(f'TCP Middleware "{name}" not found.', 'warning')
        return redirect(url_for('tcp.list_tcp_middlewares'))

    mw_type_obj, mw_config = existing

    if request.method == 'POST':
        mw_type = request.form.get('middleware_type', '').strip()
        try:
            if mw_type == TCPMiddlewareType.IN_FLIGHT_CONN.value:
                cm.create_tcp_middleware(
                    name, TCPMiddlewareType.IN_FLIGHT_CONN,
                    {'amount': _parse_int(request.form.get('amount', '10'), 10)},
                )
            elif mw_type == TCPMiddlewareType.IP_ALLOW_LIST.value:
                cm.create_tcp_middleware(
                    name, TCPMiddlewareType.IP_ALLOW_LIST,
                    {'sourceRange': _parse_csv(request.form.get('source_range', ''))},
                )
            else:
                flash('Unknown TCP middleware type.', 'danger')
                return render_template(
                    'tcp/middlewares/edit.html',
                    mw_name=name, form_data=request.form,
                    mw_type=mw_type_obj.value, mw_config=mw_config,
                )
            flash(f'TCP Middleware "{name}" updated!', 'success')
            return redirect(url_for('tcp.list_tcp_middlewares'))
        except Exception as exc:
            flash(f'Error: {str(exc)}', 'danger')
        return render_template(
            'tcp/middlewares/edit.html',
            mw_name=name, form_data=request.form,
            mw_type=mw_type_obj.value, mw_config=mw_config,
        )

    return render_template(
        'tcp/middlewares/edit.html',
        mw_name=name, form_data={},
        mw_type=mw_type_obj.value, mw_config=mw_config,
    )
