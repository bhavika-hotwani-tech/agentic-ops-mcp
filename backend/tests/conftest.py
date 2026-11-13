import sys
import os
import pytest
from starlette.testclient import TestClient

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)
