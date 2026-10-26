"""The HTTP API must report the package version, not a stale literal."""

import io
import json

import archaeology
from archaeology import api


class _Handler:
    def __init__(self):
        self.wfile = io.BytesIO()
        self.status = None

    def send_response(self, status):
        self.status = status

    def send_header(self, *_):
        pass

    def end_headers(self):
        pass


def test_health_reports_the_package_version():
    handler = _Handler()
    api.handle_health(handler)
    body = json.loads(handler.wfile.getvalue())
    assert body["version"] == archaeology.__version__


def test_api_has_no_version_of_its_own():
    assert api.__version__ is archaeology.__version__
