import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1/unused")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    test_session = sessionmaker(bind=test_engine, expire_on_commit=False)

    def get_test_db():
        with test_session() as session:
            yield session

    with TestClient(create_app(test_engine, get_test_db)) as test_client:
        yield test_client
    Base.metadata.drop_all(test_engine)

