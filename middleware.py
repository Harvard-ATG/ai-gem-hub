"""WSGI middleware used by app.py."""


class HealthCheckMiddleware:
    """Respond to /healthcheck at the WSGI layer, before Flask processes the request.

    ALB health checks send the container IP as the Host header and omit
    X-Forwarded-Host, which causes Werkzeug's TRUSTED_HOSTS validation to
    reject them with 400.  Handling the probe here avoids that entirely.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if environ.get('PATH_INFO') == '/healthcheck':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'ok']
        return self.app(environ, start_response)
