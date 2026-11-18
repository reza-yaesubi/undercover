import pytest
from fastapi.testclient import TestClient

from backend.database import Database
from backend.main import create_app


@pytest.fixture
def database(tmp_path):
    return Database(tmp_path / "test.sqlite3")


@pytest.fixture
def client(database):
    with TestClient(create_app(database)) as test_client:
        yield test_client
