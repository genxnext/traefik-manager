#!/usr/bin/env python3
"""Traefik Manager — thin entry point.

All application logic lives in the app/ package (Blueprint modules).
"""
import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 8090))
    debug = os.environ.get('FLASK_DEBUG', '').lower() == 'true'
    print(f'Starting Traefik Manager on http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
