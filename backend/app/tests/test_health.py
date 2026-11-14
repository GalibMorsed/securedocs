from app.schemas.health import ServiceStatus
from app.services import health_service


def _ok(name: str) -> ServiceStatus:
    return ServiceStatus(name=name, ok=True, detail="fine", latency_ms=1.0)


def _fail(name: str) -> ServiceStatus:
    return ServiceStatus(name=name, ok=False, detail="down", latency_ms=1.0)


def test_liveness(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["app"] == "SecureDocs"


def test_readiness_all_ok(client, monkeypatch):
    monkeypatch.setattr(health_service, "check_database", lambda db: _ok("PostgreSQL"))
    monkeypatch.setattr(health_service, "check_pgvector", lambda db: _ok("pgvector"))
    monkeypatch.setattr(health_service, "check_redis", lambda r: _ok("Redis"))

    res = client.get("/api/v1/health/services")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert [s["name"] for s in body["services"]] == ["PostgreSQL", "pgvector", "Redis"]


def test_readiness_degraded_returns_503(client, monkeypatch):
    monkeypatch.setattr(health_service, "check_database", lambda db: _ok("PostgreSQL"))
    monkeypatch.setattr(health_service, "check_pgvector", lambda db: _fail("pgvector"))
    monkeypatch.setattr(health_service, "check_redis", lambda r: _ok("Redis"))

    res = client.get("/api/v1/health/services")
    assert res.status_code == 503
    assert res.json()["status"] == "degraded"


def test_check_failure_is_captured_not_raised():
    class Broken:
        def ping(self):
            raise ConnectionError("connection refused")

    result = health_service.check_redis(Broken())  # type: ignore[arg-type]
    assert result.ok is False
    assert "ConnectionError" in result.detail
