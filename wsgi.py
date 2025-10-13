"""
WSGI wrapper for FastAPI app to work with waitress
"""
from asgiref.wsgi import AsgiToWsgi
from app.main import app

# Convert ASGI app to WSGI
application = AsgiToWsgi(app)