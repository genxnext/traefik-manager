"""
app/health.py — Health Blueprint.

Single endpoint used by load-balancers / container orchestrators to verify
that the app can reach etcd.
"""

from flask import Blueprint, jsonify
from app import globals as state

bp = Blueprint('health', __name__)


@bp.route('/api/health')
def health():
    """
    Return 200 + {"status": "healthy"} when etcd is reachable,
    500 + {"status": "unhealthy"} otherwise.

    Uses etcd_client.health_check() rather than a heavier list_routers() call.
    """
    try:
        if not state.etcd_client:
            return jsonify({'status': 'unhealthy', 'error': 'No etcd connection configured'}), 500

        healthy = state.etcd_client.health_check()
        if healthy:
            return jsonify({'status': 'healthy', 'etcd_url': state.etcd_url})
        return jsonify({'status': 'unhealthy', 'etcd_url': state.etcd_url}), 500

    except Exception as exc:
        return jsonify({'status': 'unhealthy', 'error': str(exc)}), 500
