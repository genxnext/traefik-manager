"""
app/__init__.py — Flask application factory.

Creates the Flask app, initialises the auth database, syncs the active etcd
connection, then registers all domain Blueprints.
"""

import os

from flask import Flask
from jinja2 import ChoiceLoader, FileSystemLoader

import auth_db as _auth_db
from app import globals as state


def _collect_template_dirs(app_dir: str) -> list:
    """
    Walk the entire app/ package tree and collect every 'templates/' subdirectory.

    This allows each sub-feature (e.g. app/http/routers/templates/) to own its
    HTML files while still being discoverable by Jinja2 at render time.
    The global app/templates/ directory (base.html, macros) is included first
    so it takes highest priority.
    """
    dirs = []
    for root, subdirs, _files in os.walk(app_dir):
        if 'templates' in subdirs:
            dirs.append(os.path.join(root, 'templates'))
    return dirs


def create_app() -> Flask:
    """Create and configure the Flask application."""
    # Global templates live in app/templates/ (base.html, macros/).
    # Each sub-feature has its own templates/ dir discovered automatically.
    _app_dir  = os.path.dirname(os.path.abspath(__file__))
    _base_dir = os.path.dirname(_app_dir)

    app = Flask(
        __name__,
        template_folder=os.path.join(_app_dir, 'templates'),
        static_folder=os.path.join(_base_dir, 'static'),
    )
    app.secret_key = os.environ.get(
        'FLASK_SECRET_KEY',
        'traefik-manager-secret-key-change-in-production',
    )

    # ── Initialise auth / connection database ─────────────────────────────────
    _auth_db.init_db(default_etcd_url=state.etcd_url)

    # ── Sync to the DB-active connection (may differ from ETCD_URL env var) ───
    _active = _auth_db.get_active_connection()
    if _active and _active['url'] != state.etcd_url:
        state._reinit_etcd(_active['url'])

    # ── Register blueprints ───────────────────────────────────────────────────
    from app.auth import bp as auth_bp
    from app.common import bp as common_bp
    from app.http import bp as http_bp
    from app.tcp import bp as tcp_bp
    from app.udp import bp as udp_bp
    from app.tls import bp as tls_bp
    from app.config import bp as config_bp
    from app.health import bp as health_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(common_bp)
    app.register_blueprint(http_bp)
    app.register_blueprint(tcp_bp)
    app.register_blueprint(udp_bp)
    app.register_blueprint(tls_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)

    # ── Auto-discover ALL templates/ dirs under app/ and wire into Jinja2 ────
    # This lets every sub-feature (e.g. app/http/routers/templates/) own its
    # HTML files without requiring a per-subfolder Blueprint registration.
    # Exclude the global app/templates/ already set as Flask's template_folder.
    _global_tmpl = os.path.join(_app_dir, 'templates')
    _tmpl_dirs   = [d for d in _collect_template_dirs(_app_dir) if d != _global_tmpl]
    _fs_loaders  = [FileSystemLoader(d) for d in _tmpl_dirs if os.path.isdir(d)]
    app.jinja_loader = ChoiceLoader([app.jinja_loader] + _fs_loaders)

    return app
