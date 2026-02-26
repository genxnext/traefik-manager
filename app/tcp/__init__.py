"""app/tcp/ — TCP feature package."""
from flask import Blueprint

bp = Blueprint('tcp', __name__)

# Import sub-modules to register routes
from app.tcp.routers import views as _r      # noqa: F401
from app.tcp.services import views as _s     # noqa: F401
from app.tcp.middlewares import views as _m  # noqa: F401
