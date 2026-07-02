"""Seed the Rigel app catalog. Idempotent (upsert by key).

Run standalone:  python seed.py
Also invoked from app startup.

Each entry carries a full download_url (or a web link when is_web=True).
Re-seeding preserves an app's latest_version, and preserves a download_url
already set by a release when the seed leaves it blank (COX "coming soon").
"""
import db

NOC = "https://releases.vivesincables.com/dl/nocboard"
DN = "https://releases.vivesincables.com/dl/doctornet"
ATLAS = "https://releases.vivesincables.com/dl/atlas"

SEED_APPS = [
    # ---- NOCBoard family (monitoring) ----
    {"key": "nocboard-wl", "name": "NOCBoard WL",
     "description": "Monitoreo de infraestructura inalambrica (radios, enlaces).",
     "download_url": f"{NOC}/NOCBoard-latest.dmg", "icon_emoji": "📡", "is_public": False},
    {"key": "nocboard-datos", "name": "NOCBoard Datos",
     "description": "Monitoreo de cores y switches de la red de datos.",
     "download_url": f"{NOC}/NOCBoard-Datos-latest.dmg", "icon_emoji": "🖧", "is_public": True},
    {"key": "nocboard-cx", "name": "NOCBoard CX",
     "description": "Monitoreo de infraestructura de clientes.",
     "download_url": f"{NOC}/NOCBoard-CX-latest.dmg", "icon_emoji": "🏢", "is_public": False},
    {"key": "nocboard-cx-datos", "name": "NOCBoard CX-Datos",
     "description": "Monitoreo de routers de clientes.",
     "download_url": f"{NOC}/NOCBoard-CX-Datos-latest.dmg", "icon_emoji": "🔌", "is_public": False},
    {"key": "nocboard-energia", "name": "NOCBoard Energia",
     "description": "Monitoreo de energia: CFE y baterias.",
     "download_url": f"{NOC}/NOCBoard-Energia-latest.dmg", "icon_emoji": "🔋", "is_public": True},

    # ---- Atlas ----
    {"key": "atlas", "name": "Atlas Notes OS",
     "description": "Compilador de conocimiento macOS: notas -> Obsidian, OCR, IA.",
     "download_url": f"{ATLAS}/Atlas-v0.1.0.dmg", "icon_emoji": "📓", "is_public": True},

    # ---- DoctorNet (macOS) ----
    {"key": "doctornet-macos", "name": "DoctorNet (macOS)",
     "description": "Diagnostico de red: Traceroute, MTR, iPerf, Path.",
     "download_url": f"{DN}/DoctorNet-latest.dmg", "icon_emoji": "🩺", "is_public": True},

    # ---- Pulso Directo (web platform) ----
    {"key": "pulso-directo", "name": "Pulso Directo",
     "description": "Plataforma web de denuncias + IA (multi-empresa).",
     "download_url": "https://pulso.dp01.vivesincables.com/", "icon_emoji": "🗣️",
     "is_public": True, "is_web": True},

    # ---- COX — Copilotos XCIEN (6 macOS apps; DMGs proximamente) ----
    {"key": "cox-tecnico", "name": "COX Tecnico",
     "description": "Copiloto de NOC: alarmas, diagnosticos, incidentes.",
     "download_url": "", "icon_emoji": "🛠️", "is_public": False},
    {"key": "cox-atencion", "name": "COX Atencion",
     "description": "Customer 360, retencion, health scoring.",
     "download_url": "", "icon_emoji": "🎧", "is_public": False},
    {"key": "cox-central", "name": "COX Central",
     "description": "Consola central de operaciones.",
     "download_url": "", "icon_emoji": "🧭", "is_public": False},
    {"key": "cox-comercial", "name": "COX Comercial",
     "description": "Pipeline de ventas y cotizaciones.",
     "download_url": "", "icon_emoji": "💼", "is_public": False},
    {"key": "cox-preventa", "name": "COX Preventa",
     "description": "Pre-factibilidad y preventa (fibra / inalambrica).",
     "download_url": "", "icon_emoji": "📍", "is_public": False},
    {"key": "cox-rh", "name": "COX RH",
     "description": "Recursos humanos: contratos y seguimiento.",
     "download_url": "", "icon_emoji": "👥", "is_public": False},
]


def seed():
    db.init_db()
    for a in SEED_APPS:
        existing = db.get_app(a["key"])
        latest_version = existing["latest_version"] if existing else ""
        # Keep a URL a release already set if this seed entry has none (COX).
        download_url = a["download_url"] or (existing["download_url"] if existing else "")
        db.upsert_app(
            key=a["key"],
            name=a["name"],
            description=a["description"],
            download_url=download_url,
            latest_version=latest_version,
            icon_emoji=a["icon_emoji"],
            is_public=a.get("is_public", False),
            is_web=a.get("is_web", False),
        )
    return db.list_apps()


if __name__ == "__main__":
    apps = seed()
    print(f"Seeded {len(apps)} apps:")
    for a in apps:
        vis = "public" if a["is_public"] else "private"
        kind = "web" if a.get("is_web") else "dmg"
        print(f"  {a['icon_emoji']} {a['key']:20s} [{vis}/{kind}] -> {a['download_url'] or '(proximamente)'}")
