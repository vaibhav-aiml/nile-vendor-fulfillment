import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import geoalchemy2.admin as ga_admin

# Disable SpatiaLite DDL operations in SQLite unit tests
class DummyDialect:
    @staticmethod
    def before_create(table, bind, **kw): pass
    @staticmethod
    def after_create(table, bind, **kw): pass
    @staticmethod
    def before_drop(table, bind, **kw): pass
    @staticmethod
    def after_drop(table, bind, **kw): pass

ga_admin.select_dialect = lambda name: DummyDialect()

from app.core.database import Base, get_db
from app.core.config import settings
from app.workers.celery_app import celery_app
from app.main import app as fastapi_app

import app.core.database as app_db
import app.workers.tasks as app_tasks

from sqlalchemy.pool import StaticPool

# In-memory SQLite database for testing with StaticPool so threads share the same in-memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def setup_sqlite_spatial_dummies(dbapi_conn, record):
    """Provide dummy GIS functions so SQLite executes GeoAlchemy queries in tests."""
    dbapi_conn.create_function("GeomFromEWKT", 1, lambda x: x)
    dbapi_conn.create_function("AsEWKB", 1, lambda x: x)
    dbapi_conn.create_function("CheckSpatialIndex", 2, lambda *a: 1)

# Ensure test environment has a test ops token configured
settings.OPS_AUTH_SECRET = "test_ops_secret_token"

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure background Celery tasks also use the test sessionmaker
app_db.SessionLocal = TestingSessionLocal
app_tasks.SessionLocal = TestingSessionLocal


@pytest.fixture(scope="session", autouse=True)
def setup_celery_eager():
    """Run celery tasks eagerly/synchronously during testing with in-memory broker."""
    celery_app.conf.update(
        broker_url="memory://",
        result_backend="cache+memory://",
        task_always_eager=True,
        task_eager_propagates=True,
    )


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def ops_auth_headers():
    """Headers containing the shared Ops secret token."""
    return {"X-Ops-Token": settings.OPS_AUTH_SECRET}
