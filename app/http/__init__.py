"""app/http/ — HTTP feature package."""
from flask import Blueprint

bp = Blueprint('http', __name__)

# Import sub-modules to register routes
from app.http.routers import views as _r   # noqa: F401
from app.http.services import views as _s  # noqa: F401
from app.http.middlewares import views as _m  # noqa: F401
from app.http.domains import views as _d  # noqa: F401
from app.http.servers_transports import views as _st  # noqa: F401
