# Rigel Beta (MQ-38)

Servicio tipo TestFlight: los testers se suscriben por correo a las apps de escritorio y reciben aviso de cada versión nueva. Mesquite (recibido de Rigel Open Labs el 12 de octubre de 2026). Nivel 1, Producción, validado.
Ficha: MQ-38 en el registro de fichas de Mesquite AI. Responsable técnico: Por definir. Valida: por definir. Revisado: 2026-10-13.

## Stack

Python, FastAPI, SQLite y Jinja2. Python en [Dockerfile.prod](Dockerfile.prod); librerías en [requirements.txt](requirements.txt). Correo por Resend. Corre en Dokploy con [docker-compose.yml](docker-compose.yml).

## Comandos

Fuente: [README.md](README.md), «Run locally».

| Para | Comando |
| --- | --- |
| Instalar | `python3.13 -m venv .venv` y `.venv/bin/pip install -r requirements.txt` |
| Correr en local | `.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9486` |
| Pruebas | `.venv/bin/pytest -q` |

Migraciones, despliegue y publicación de DMG: [docs/backend.md](docs/backend.md).

## Mapa: qué leer antes de tocar algo

| Si vas a tocar… | Lee |
| --- | --- |
| Pantallas | «Frontend» de este archivo |
| Datos, API, roles, integraciones, despliegue o publicar un DMG | [docs/backend.md](docs/backend.md) |
| Detalle de endpoints, variables y Resend | [README.md](README.md) |

## Frontend

Páginas Jinja2 en `templates/`: `base.html`, `landing.html` (lista de apps y formulario, la sirve `GET /` en `app.py`) y `result.html` (mensajes de confirmación). Textos en español, sin acentos.

## Reglas

- Un cambio que contradiga un documento lo actualiza en el mismo commit.
- Las pruebas corren sin `RESEND_API_KEY`: modo DEV, sin red.

## Prohibido

- Escribir secretos en el repo: van en variables de entorno y en el gestor de contraseñas ([POR CONFIRMAR: nombre del gestor]).
- Contraseñas o llaves por defecto en producción.
- Cambiar el esquema de la base sin su migración en `db.py`.

## No incluye

Distribución en tiendas de apps (ficha MQ-38, §4).

## Riesgos abiertos

Detalle en la revisión de seguridad de valores por defecto (13 oct 2026). Ruta · tipo.

- Crítica · [config.py](config.py), [docker-compose.yml](docker-compose.yml), [notify-beta.sh](notify-beta.sh), [README.md](README.md) · llave de administración por defecto (dev), publicada en el README. Si producción no define `BETA_ADMIN_KEY`, la API de administración la acepta.
- Media · [notify-beta.sh](notify-beta.sh) · apunta a producción por defecto, con la llave por defecto; el README dice que el valor por defecto es local.
- Media · [notify-beta.sh](notify-beta.sh) · la llave viaja como argumento de `curl` y se ve en `ps`.
- Media · [app.py](app.py) (`/subscribe`) · sin límite de envíos ni CAPTCHA: se puede usar para mandar correos a terceros.
- Media · [app.py](app.py), [seed.py](seed.py) · `is_public` se guarda pero nunca se aplica: las apps privadas salen en la landing y admiten suscripción.
- Baja · [config.py](config.py), [docker-compose.yml](docker-compose.yml) · `BASE_URL` por defecto es localhost: los enlaces de confirmar y cancelar no funcionan.
- Baja · [app.py](app.py) (`/subscribe`) · revela si un correo ya está suscrito («Ya estabas suscrito»).
- Baja · [app.py](app.py) (`require_admin`) · la llave se compara sin tiempo constante, sin límite de intentos y sin registro de auditoría.
- Baja · [db.py](db.py) · tokens sin caducidad; el de confirmar es el mismo que el de cancelar.
- Baja · [email_resend.py](email_resend.py) · `notes`, `version`, `name` y `download_url` van sin escapar en el HTML del correo; `download_url` acepta cualquier esquema.
- Baja · [email_resend.py](email_resend.py), [app.py](app.py) · sin llave de Resend nada se envía pero la API responde que sí; los correos de destino quedan en el log (dato personal).
- Baja · [Dockerfile.prod](Dockerfile.prod) · sin `.dockerignore` (`COPY . .` puede meter `.env` o `.db` locales) y el proceso corre como root.
- Baja · [publish-release.sh](publish-release.sh) · `--beta-key` es la `app_key` pero se confunde con la llave de administración, y se imprime.
- Datos personales · base SQLite de producción (fuera del repo) · correos de testers.
