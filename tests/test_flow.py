"""End-to-end tests using FastAPI TestClient. Email runs in DEV mode (no network)."""
import os
import tempfile

import pytest

# Configure env BEFORE importing the app so config picks up the temp DB + dev mode.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["BETA_DB_PATH"] = _tmp.name
os.environ.pop("RESEND_API_KEY", None)  # ensure DEV mode (no network)
os.environ["BETA_ADMIN_KEY"] = "test-admin-key"
os.environ["BASE_URL"] = "http://testserver"

from fastapi.testclient import TestClient  # noqa: E402
import app as app_module  # noqa: E402

client = TestClient(app_module.app)
ADMIN = {"X-API-Key": "test-admin-key"}


@pytest.fixture(autouse=True)
def _ensure_seeded():
    # startup event runs via TestClient context; nothing else needed
    yield


def test_landing_ok():
    r = client.get("/")
    assert r.status_code == 200
    assert "RIGEL BETA" in r.text
    assert "NOCBoard Datos" in r.text


def test_admin_requires_api_key():
    # no header
    assert client.get("/api/apps").status_code == 401
    # wrong key
    assert client.get("/api/apps", headers={"X-API-Key": "nope"}).status_code == 401
    # correct key
    r = client.get("/api/apps", headers=ADMIN)
    assert r.status_code == 200
    assert any(a["key"] == "nocboard-energia" for a in r.json())


def test_releases_requires_api_key():
    body = {"app_key": "nocboard-datos", "version": "9.9.9"}
    assert client.post("/api/releases", json=body).status_code == 401


def test_full_subscribe_confirm_release_unsubscribe():
    email = "tester@example.com"
    app_key = "nocboard-energia"

    # 1) subscribe (multipart form; app_keys repeated)
    r = client.post(
        "/subscribe",
        data={"email": email, "app_keys": [app_key]},
    )
    assert r.status_code == 200
    assert "Revisa tu correo" in r.text

    # grab the pending subscription token straight from the DB layer
    import db
    subscriber = db.upsert_subscriber(email)
    subs = db.list_subscribers_for_app(app_key)
    mine = [s for s in subs if s["email"] == email]
    assert mine and mine[0]["status"] == "pending"
    token = mine[0]["token"]

    # before confirm: no confirmed recipients
    assert db.confirmed_subscribers_for_app(app_key) == []

    # 2) confirm
    r = client.get(f"/confirm/{token}")
    assert r.status_code == 200
    assert "confirmada" in r.text.lower()

    recipients = db.confirmed_subscribers_for_app(app_key)
    assert any(rc["email"] == email for rc in recipients)

    # 3) release -> should send to the confirmed subscriber (DEV mode, ok)
    r = client.post(
        "/api/releases",
        headers=ADMIN,
        json={
            "app_key": app_key,
            "version": "3.5.0",
            "notes": "Fix crash en arranque.",
        },
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["sent"] >= 1
    assert payload["recipients"] >= 1

    # app.latest_version got bumped
    a = db.get_app(app_key)
    assert a["latest_version"] == "3.5.0"

    # 4) unsubscribe
    r = client.get(f"/unsubscribe/{token}")
    assert r.status_code == 200
    assert "cancel" in r.text.lower()

    # after unsubscribe: no longer a confirmed recipient
    recipients = db.confirmed_subscribers_for_app(app_key)
    assert all(rc["email"] != email for rc in recipients)

    # a new release now sends to 0 (this email) -- confirm count dropped
    r = client.post(
        "/api/releases",
        headers=ADMIN,
        json={"app_key": app_key, "version": "3.5.1"},
    )
    assert r.status_code == 200
    assert all(s["email"] != email or s["status"] == "unsubscribed"
               for s in db.list_subscribers_for_app(app_key))


def test_subscribe_rejects_bad_email():
    r = client.post("/subscribe", data={"email": "notanemail", "app_keys": ["nocboard-wl"]})
    assert r.status_code == 400


def test_subscribe_requires_app_selection():
    r = client.post("/subscribe", data={"email": "x@example.com"})
    assert r.status_code == 400


def test_release_unknown_app_404():
    r = client.post("/api/releases", headers=ADMIN,
                    json={"app_key": "does-not-exist", "version": "1.0.0"})
    assert r.status_code == 404


def test_upsert_app_idempotent():
    body = {
        "key": "test-app", "name": "Test App", "description": "d",
        "download_url": "https://example.com/x.dmg", "is_public": True,
    }
    r1 = client.post("/api/apps", headers=ADMIN, json=body)
    assert r1.status_code == 200
    body["name"] = "Test App Renamed"
    r2 = client.post("/api/apps", headers=ADMIN, json=body)
    assert r2.status_code == 200
    assert r2.json()["name"] == "Test App Renamed"
    # still only one row for that key
    import db
    assert db.get_app("test-app")["name"] == "Test App Renamed"
