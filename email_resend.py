"""Email delivery via Resend HTTP API, with a network-free DEV mode.

If RESEND_API_KEY is not set we never touch the network: we just print a line
so the whole flow can be exercised locally and in tests without credentials.
"""
import httpx

from config import config

RESEND_URL = "https://api.resend.com/emails"


def send(to: str, subject: str, html: str) -> dict:
    """Send one email. Returns a small dict {ok, mode, [id|error]}.

    DEV mode (no RESEND_API_KEY): prints and returns ok without any HTTP call.
    """
    if not config.RESEND_API_KEY:
        print(f"[beta-email DEV] to={to} subject={subject!r}")
        return {"ok": True, "mode": "dev", "to": to}

    payload = {
        "from": config.FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    headers = {
        "Authorization": f"Bearer {config.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(RESEND_URL, json=payload, headers=headers, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        return {"ok": True, "mode": "live", "id": data.get("id"), "to": to}
    except Exception as exc:  # noqa: BLE001 - we never want a send to crash the request
        print(f"[beta-email ERROR] to={to} subject={subject!r} error={exc}")
        return {"ok": False, "mode": "live", "error": str(exc), "to": to}


# ---------- HTML templates ----------

_WRAP = """\
<div style="background:#0b0f14;padding:32px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:520px;margin:0 auto;background:#111820;border:1px solid #1c2630;border-radius:12px;overflow:hidden;">
    <div style="padding:20px 28px;border-bottom:1px solid #1c2630;">
      <span style="color:#22d3ee;font-weight:700;font-size:18px;letter-spacing:.5px;">RIGEL BETA</span>
    </div>
    <div style="padding:28px;color:#c7d2dc;font-size:15px;line-height:1.6;">
      {body}
    </div>
    <div style="padding:16px 28px;border-top:1px solid #1c2630;color:#5b6b78;font-size:12px;">
      {footer}
    </div>
  </div>
</div>"""


def _btn(href: str, label: str) -> str:
    return (
        f'<a href="{href}" style="display:inline-block;background:#22d3ee;color:#06141a;'
        f'font-weight:700;text-decoration:none;padding:11px 22px;border-radius:8px;'
        f'font-size:14px;">{label}</a>'
    )


def confirmation_html(apps, confirm_url: str) -> str:
    """apps: list of dicts with name/icon_emoji. confirm_url: the confirm link."""
    items = "".join(
        f'<li style="margin:4px 0;">{a.get("icon_emoji","")} <b style="color:#e7eef4;">{a["name"]}</b></li>'
        for a in apps
    )
    body = f"""\
<p style="margin:0 0 14px;color:#e7eef4;font-size:17px;font-weight:600;">Confirma tu suscripcion</p>
<p style="margin:0 0 12px;">Te suscribiste para recibir avisos de nuevas versiones de:</p>
<ul style="margin:0 0 20px;padding-left:18px;">{items}</ul>
<p style="margin:0 0 20px;">Confirma para empezar a recibir correos cuando salga una nueva beta.</p>
<p style="margin:0 0 8px;">{_btn(confirm_url, "Confirmar todas")}</p>
<p style="margin:18px 0 0;color:#5b6b78;font-size:12px;">Si no fuiste tu, ignora este correo y no pasara nada.</p>"""
    footer = "Rigel Open Labs &middot; distribucion de betas de escritorio"
    return _WRAP.format(body=body, footer=footer)


def new_version_html(app, version: str, download_url: str, notes: str,
                     unsubscribe_url: str) -> str:
    notes_block = (
        f'<div style="background:#0b1219;border:1px solid #1c2630;border-radius:8px;'
        f'padding:14px;margin:0 0 20px;color:#9fb0bd;font-size:14px;white-space:pre-wrap;">{notes}</div>'
        if notes else ""
    )
    body = f"""\
<p style="margin:0 0 14px;color:#e7eef4;font-size:17px;font-weight:600;">
  {app.get("icon_emoji","")} {app["name"]} &mdash; nueva version disponible</p>
<p style="margin:0 0 16px;">Ya esta lista la version <b style="color:#22d3ee;">v{version}</b>.</p>
{notes_block}
<p style="margin:0 0 8px;">{_btn(download_url, "Descargar")}</p>
<p style="margin:18px 0 0;color:#5b6b78;font-size:12px;">Liga directa: {download_url}</p>"""
    footer = (
        'Recibes esto porque te suscribiste a la beta. '
        f'<a href="{unsubscribe_url}" style="color:#5b6b78;">Cancelar suscripcion</a>.'
    )
    return _WRAP.format(body=body, footer=footer)
