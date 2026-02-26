"""app/udp/ — UDP feature package."""
from flask import Blueprint

bp = Blueprint('udp', __name__)

# Import sub-modules to register routes
from app.udp.routers import views as _r   # noqa: F401
from app.udp.services import views as _s  # noqa: F401
