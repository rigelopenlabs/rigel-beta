"""Seed the NOCBoard family apps. Idempotent (upsert by key).

Run standalone:  python seed.py
Also invoked from app startup.
"""
import db

RELEASES_BASE = "https://releases.vivesincables.com/dl/nocboard"

SEED_APPS = [
    {
        "key": "nocboard-wl",
        "name": "NOCBoard WL",
        "description": "Monitoreo de infraestructura inalambrica (radios, enlaces).",
        "dmg": "NOCBoard-latest.dmg",
        "icon_emoji": "\U0001F4E1",  # satellite antenna
        "is_public": False,  # Drive
    },
    {
        "key": "nocboard-datos",
        "name": "NOCBoard Datos",
        "description": "Monitoreo de cores y switches de la red de datos.",
        "dmg": "NOCBoard-Datos-latest.dmg",
        "icon_emoji": "\U0001F5A7",  # networked nodes
        "is_public": True,
    },
    {
        "key": "nocboard-cx",
        "name": "NOCBoard CX",
        "description": "Monitoreo de infraestructura de clientes.",
        "dmg": "NOCBoard-CX-latest.dmg",
        "icon_emoji": "\U0001F3E2",  # office building
        "is_public": False,  # Drive
    },
    {
        "key": "nocboard-cx-datos",
        "name": "NOCBoard CX-Datos",
        "description": "Monitoreo de routers de clientes.",
        "dmg": "NOCBoard-CX-Datos-latest.dmg",
        "icon_emoji": "\U0001F50C",  # plug
        "is_public": False,  # Drive
    },
    {
        "key": "nocboard-energia",
        "name": "NOCBoard Energia",
        "description": "Monitoreo de energia: CFE y baterias.",
        "dmg": "NOCBoard-Energia-latest.dmg",
        "icon_emoji": "\U0001F50B",  # battery
        "is_public": True,
    },
]


def seed():
    db.init_db()
    for a in SEED_APPS:
        existing = db.get_app(a["key"])
        latest_version = existing["latest_version"] if existing else ""
        db.upsert_app(
            key=a["key"],
            name=a["name"],
            description=a["description"],
            download_url=f"{RELEASES_BASE}/{a['dmg']}",
            latest_version=latest_version,
            icon_emoji=a["icon_emoji"],
            is_public=a["is_public"],
        )
    return db.list_apps()


if __name__ == "__main__":
    apps = seed()
    print(f"Seeded {len(apps)} apps:")
    for a in apps:
        vis = "public" if a["is_public"] else "private"
        print(f"  {a['icon_emoji']} {a['key']:18s} [{vis}] -> {a['download_url']}")
