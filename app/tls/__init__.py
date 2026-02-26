"""app/tls/ — TLS feature package."""
from flask import Blueprint

bp = Blueprint('tls', __name__)

# Import sub-modules to register routes
from app.tls.options import views as _o  # noqa: F401
from app.tls.stores import views as _s   # noqa: F401
