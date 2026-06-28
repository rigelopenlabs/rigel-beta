"""rigel-beta: a 'TestFlight for Rigel desktop apps'.

Users subscribe to in-development apps and get an email when a new version ships.
FastAPI + SQLite + Resend (HTTP) + Jinja2. No Postgres.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db
import email_resend
from config import config
from seed import seed

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    seed()
    yield


app = FastAPI(
    title="rigel-beta",
    description="Desktop beta distribution + subscriptions",
    lifespan=lifespan,
)

# Initialize + seed at import time too, so the DB is ready even when the app is
# used without triggering the lifespan (e.g. ad-hoc TestClient calls).
db.init_db()
seed()


# ---------- auth helper ----------

def require_admin(x_api_key: str | None):
    if not x_api_key or x_api_key != config.ADMIN_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


# =========================================================
# Public pages
# =========================================================

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    apps = db.list_apps()
    return templates.TemplateResponse(request, "landing.html", {"apps": apps})


@app.post("/subscribe", response_class=HTMLResponse)
def subscribe(request: Request, email: str = Form(...),
              app_keys: list[str] = Form(default=[])):
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="invalid email")
    if not app_keys:
        raise HTTPException(status_code=400, detail="select at least one app")

    subscriber = db.upsert_subscriber(email)

    chosen_apps = []
    primary_token = None
    for key in app_keys:
        a = db.get_app(key)
        if not a:
            continue
        sub = db.upsert_subscription(subscriber["id"], key)
        chosen_apps.append(a)
        # Use the token of the first still-pending subscription as the confirm token.
        if primary_token is None and sub["status"] == "pending":
            primary_token = sub["token"]

    if not chosen_apps:
        raise HTTPException(status_code=400, detail="no valid apps selected")

    # If everything was already confirmed there is nothing to confirm.
    if primary_token is None:
        return templates.TemplateResponse(
            request,
            "result.html",
            {
                "title": "Ya estabas suscrito",
                "message": "Ya tenias confirmadas todas esas apps. No hicimos nada nuevo.",
            },
        )

    confirm_url = f"{config.BASE_URL}/confirm/{primary_token}"
    html = email_resend.confirmation_html(chosen_apps, confirm_url)
    email_resend.send(email, "Confirma tu suscripcion a Rigel Beta", html)

    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": "Revisa tu correo",
            "message": f"Te enviamos un correo a {email} con un link para confirmar "
                       "tu suscripcion. Confirma para empezar a recibir avisos.",
        },
    )


@app.get("/confirm/{token}", response_class=HTMLResponse)
def confirm(request: Request, token: str):
    confirmed = db.confirm_subscriptions_for_token(token)
    if confirmed is None:
        raise HTTPException(status_code=404, detail="token not found")
    keys = [c["app_key"] for c in confirmed]
    names = []
    for k in keys:
        a = db.get_app(k)
        if a:
            names.append(a["name"])
    listing = ", ".join(names) if names else "tus apps"
    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": "Suscripcion confirmada",
            "message": f"Listo. Recibiras avisos de nuevas versiones de: {listing}.",
        },
    )


@app.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(request: Request, token: str):
    sub = db.unsubscribe_by_token(token)
    if sub is None:
        raise HTTPException(status_code=404, detail="token not found")
    a = db.get_app(sub["app_key"])
    name = a["name"] if a else sub["app_key"]
    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": "Suscripcion cancelada",
            "message": f"Cancelaste tu suscripcion a {name}. No recibiras mas avisos de esa app.",
        },
    )


# =========================================================
# Admin API (X-API-Key)
# =========================================================

class AppIn(BaseModel):
    key: str
    name: str
    description: str = ""
    download_url: str = ""
    latest_version: str = ""
    icon_emoji: str = ""
    is_public: bool = False


class ReleaseIn(BaseModel):
    app_key: str
    version: str
    download_url: str = ""
    notes: str = ""


@app.post("/api/apps")
def api_upsert_app(payload: AppIn, x_api_key: str | None = Header(default=None)):
    require_admin(x_api_key)
    a = db.upsert_app(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        download_url=payload.download_url,
        latest_version=payload.latest_version,
        icon_emoji=payload.icon_emoji,
        is_public=payload.is_public,
    )
    return a


@app.get("/api/apps")
def api_list_apps(x_api_key: str | None = Header(default=None)):
    require_admin(x_api_key)
    return db.list_apps()


@app.post("/api/releases")
def api_create_release(payload: ReleaseIn, x_api_key: str | None = Header(default=None)):
    require_admin(x_api_key)
    a = db.get_app(payload.app_key)
    if not a:
        raise HTTPException(status_code=404, detail=f"unknown app_key '{payload.app_key}'")

    download_url = payload.download_url or a["download_url"]
    rel = db.insert_release(
        app_key=payload.app_key,
        version=payload.version,
        download_url=payload.download_url,  # only overrides app.download_url if non-empty
        notes=payload.notes,
    )

    # notify all confirmed subscribers
    recipients = db.confirmed_subscribers_for_app(payload.app_key)
    sent = 0
    for r in recipients:
        unsubscribe_url = f"{config.BASE_URL}/unsubscribe/{r['token']}"
        html = email_resend.new_version_html(
            app=a,
            version=payload.version,
            download_url=download_url,
            notes=payload.notes,
            unsubscribe_url=unsubscribe_url,
        )
        result = email_resend.send(
            r["email"],
            f"{a['name']} v{payload.version} disponible",
            html,
        )
        if result.get("ok"):
            sent += 1

    return {"sent": sent, "release": rel, "recipients": len(recipients)}


@app.get("/api/subscribers")
def api_subscribers(app: str, x_api_key: str | None = Header(default=None)):
    require_admin(x_api_key)
    if not db.get_app(app):
        raise HTTPException(status_code=404, detail=f"unknown app '{app}'")
    return db.list_subscribers_for_app(app)


@app.get("/health")
def health():
    return {"ok": True, "service": "rigel-beta"}
