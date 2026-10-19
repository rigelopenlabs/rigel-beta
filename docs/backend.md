# Backend · Rigel Beta

Revisado: 2026-10-13

Reglas y riesgos abiertos: [AGENTS.md](../AGENTS.md). Endpoints, variables, Resend y Dokploy ya están en [README.md](../README.md); aquí se enlazan y se anota lo que el README no dice.

## Arquitectura

Un solo componente: una app FastAPI ([app.py](../app.py)) con SQLite ([db.py](../db.py)) y correo por Resend ([email_resend.py](../email_resend.py)). La configuración sale de variables de entorno ([config.py](../config.py)). Al importar `app.py` y al arrancar, se crea el esquema y se carga el catálogo ([seed.py](../seed.py)).

Dos scripts acompañan al servicio: [notify-beta.sh](../notify-beta.sh) (avisa una versión) y [publish-release.sh](../publish-release.sh) (publica un DMG y avisa; ver «Contratos»).

## Datos

Esquema y migración viven dentro de [db.py](../db.py): la constante `SCHEMA` y la función `init_db`. No hay herramienta de migraciones. Una columna nueva se agrega con un `ALTER TABLE` condicional dentro de `init_db`, como se hizo con `is_web`.

El modelo del [README](../README.md#data-model-sqlite) omite la columna `is_web` de `apps` (aparece en `SCHEMA` y en el cuerpo de `POST /api/apps`). Estados, alta por clave, confirmación y releases están en el README: [modelo de datos](../README.md#data-model-sqlite) y [endpoints](../README.md#endpoints).

| Entidad | Para qué | Reglas que no se ven en el esquema |
| --- | --- | --- |
| apps | Catálogo de apps (DMG o web) | Cada arranque vuelve a cargar el catálogo de `seed.py`: sobrescribe nombre, descripción y visibilidad de las apps del catálogo, y conserva la última versión y, si el catálogo no trae URL, la que dejó un release. |
| subscribers | Un correo, una sola vez | El correo se guarda en minúsculas. |
| subscriptions | Un correo suscrito a una app | Volver a suscribirse a una app no confirmada genera token nuevo; una ya confirmada no cambia. |

## API

Rutas: [app.py](../app.py). Detalle de cada una: [README, «Endpoints»](../README.md#endpoints).

- Páginas públicas y `/health`: sin autenticación. Confirmar y cancelar se hacen con el token de la suscripción, en la URL.
- Rutas `/api/*`: encabezado `X-API-Key`.
- Errores: `HTTPException` de FastAPI (`{"detail": …}`) con 400, 401 y 404.

## Roles y permisos

No hay cuentas, sesiones ni roles de usuario. Hay dos actores.

| Actor | Puede | No puede | Dónde se revisa |
| --- | --- | --- | --- |
| Visitante o tester | Ver la landing, suscribirse, confirmar y cancelar con su token | Llamar a `/api/*` | Sin revisión: las rutas públicas están abiertas |
| Administrador (llave de API) | Todo `/api/*`: alta de apps, releases con envío de correos, listar suscriptores | Sin otros límites | `require_admin` en [app.py](../app.py), llamado al inicio de cada ruta `/api/*` |

Sobre `is_public`: [AGENTS.md, «Riesgos abiertos»](../AGENTS.md#riesgos-abiertos).

## Integraciones

| Sistema | Para qué | Credencial (entrada en el gestor) | Si falla… |
| --- | --- | --- | --- |
| Resend | Enviar los correos de confirmación y de nueva versión ([README, «Resend setup»](../README.md#resend-setup-production-email)) | [POR CONFIRMAR: entrada en el gestor de `RESEND_API_KEY`] [POR CONFIRMAR: si el dominio de envío está verificado en Resend] | Un envío fallido se imprime en el log y no rompe la petición; `/api/releases` no lo cuenta como enviado. Sin llave: [AGENTS.md, «Riesgos abiertos»](../AGENTS.md#riesgos-abiertos). |
| Dokploy | Corre el servicio ([README, «Deploy on Dokploy»](../README.md#deploy-on-dokploy-dp01)) | [POR CONFIRMAR: entrada en el gestor de Dokploy] | Sin servicio, no hay landing ni avisos. |
| Servidor de releases (`rigel-releases`) | Aloja los DMG públicos que `publish-release.sh` sube | [POR CONFIRMAR: entrada en el gestor y repo donde vive `rigel-releases`] [POR CONFIRMAR: entrada en el gestor de `RIGEL_DEPLOY_HOOK`, el webhook de Dokploy que usa `publish-release.sh`] | `publish-release.sh` se detiene antes de avisar. |
| Scripts de aviso | [notify-beta.sh](../notify-beta.sh) y [publish-release.sh](../publish-release.sh) llaman a `/api/releases` ([README, «Config»](../README.md#config-env-vars-dev-defaults)) | Llave de administración (`BETA_ADMIN_KEY`): [POR CONFIRMAR: entrada en el gestor] | Sin llave válida, la API responde 401 y no se avisa. |

## Despliegue y entornos

| Entorno | Dónde corre | URL | Cómo se despliega |
| --- | --- | --- | --- |
| Producción | Dokploy, servicio Compose desde [docker-compose.yml](../docker-compose.yml) (imagen de [Dockerfile.prod](../Dockerfile.prod)) | beta.vivesincables.com (ficha MQ-38 §6). En el repo aparece como valor por defecto en [notify-beta.sh](../notify-beta.sh) y [publish-release.sh](../publish-release.sh), y como ejemplo en el [README](../README.md#deploy-on-dokploy-dp01) | Pasos en [README, «Deploy on Dokploy»](../README.md#deploy-on-dokploy-dp01) |
| Local | `uvicorn` en la máquina | puerto en [config.py](../config.py) (`BASE_URL`) | Comandos en [AGENTS.md](../AGENTS.md#comandos) |

La base SQLite persiste en el volumen del compose ([README, «Deploy on Dokploy»](../README.md#deploy-on-dokploy-dp01)). [POR CONFIRMAR: quién respalda ese volumen y cada cuánto].

Variables de entorno: nombres y valores por defecto en [config.py](../config.py) y [docker-compose.yml](../docker-compose.yml); explicación en [README, «Config»](../README.md#config-env-vars-dev-defaults). [POR CONFIRMAR: cuáles están definidas en Dokploy; las de administración y de Resend son las que importan].

## Seguridad

- Usuarios semilla: no hay. El catálogo de `seed.py` solo trae apps. La llave de administración por defecto es un riesgo abierto, ver [AGENTS.md](../AGENTS.md#riesgos-abiertos).
- Registro abierto: sí. Cualquiera puede suscribirse desde la landing, con doble confirmación por correo.
- Datos sensibles: correos de los testers, en la base SQLite; ver [AGENTS.md](../AGENTS.md#riesgos-abiertos).

## Contratos con otros sistemas

`publish-release.sh` publica los DMG de las apps de escritorio, así que es un contrato que usan otros repos (regla 7 del kit). Vive aquí; los repos de las apps lo llaman y no lo copian. El flujo de cada modo (`public` y `drive`) está en [README, «Publishing a release»](../README.md#publishing-a-release-publish-releasesh); las variables y opciones, en la cabecera de [publish-release.sh](../publish-release.sh).

Lo que el script exige de cada app (`--repo`):
- Un `project.yml` con `MARKETING_VERSION`.
- Un `build-dmg.sh` con `DMG_BASENAME` o `APP_NAME`.
- Los DMG ya construidos en `dist/`: `<nombre>-v<versión>.dmg` y `<nombre>-latest.dmg`.
- `--beta-key` es la `app_key` del catálogo ([seed.py](../seed.py)), no la llave de administración.

El aviso final lo hace [notify-beta.sh](../notify-beta.sh) contra `POST /api/releases` ([README, «notify-beta.sh»](../README.md#notify-betash)). Si cambian sus argumentos, se actualiza `publish-release.sh`.
