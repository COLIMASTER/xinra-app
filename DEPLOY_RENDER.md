## Arquitectura de producción

- **Backend**: Flask (app factory `app.create_app`) ejecutado con **gunicorn**.
- **Plataforma**: Render (Free Web Service).
- **Base de datos**: PostgreSQL gestionado en **Neon** (cluster externo).
- **Almacenamiento de archivos**: sistema de archivos efímero de Render en `UPLOADS_DIR` (por defecto `./uploads`, accesible vía `/uploads`). Para producción real se recomienda S3/GCS.

---

## Variables de entorno (Render y local)

Config por código en `app/config.py`. Las claves importantes son:

- `FLASK_ENV`
  - `development` para local.
  - `production` en Render.
- `FLASK_DEBUG`
  - `1` en local si quieres recarga y debugger.
  - No definir (o `0`) en producción.
- `SECRET_KEY`
  - Obligatorio en producción.
  - Usa un valor largo y aleatorio.
- `SQLALCHEMY_DATABASE_URI`
  - **Obligatorio en producción**. Si falta y `FLASK_ENV=production`, la app lanza error al arrancar.
  - Ejemplo Neon: `postgresql+psycopg2://USER:PASSWORD@HOST/neondb?sslmode=require&channel_binding=require`.
- `UPLOADS_DIR`
  - Local: `./uploads`.
  - Render: `/opt/render/project/src/uploads` (o similar dentro del repo).
- `MAX_IMAGE_MB`
  - Por defecto `2`.
- `RATELIMIT_DEFAULT` (opcional)
  - Por defecto `100 per minute`.

Render también define `PORT` automáticamente. No hace falta declarar `PORT` a mano, solo usarlo en gunicorn.

---

## Levantar el proyecto en local usando Neon

1. **Clonar el repo y crear entorno virtual**
   - `git clone git@github.com:COLIMASTER/xinra-app.git`
   - `cd xinra-app/flask_app`
   - `python -m venv .venv`
   - Activar entorno (`.\.venv\Scripts\activate` en Windows).
   - `pip install -r requirements.txt`

2. **Configurar `.env` para usar Neon**
   - Copiar `.env.example` a `.env`.
   - Ajustar:
     - `FLASK_ENV=development`
     - `FLASK_DEBUG=1`
     - `SECRET_KEY=algo_seguro_para_local`
     - `SQLALCHEMY_DATABASE_URI=<URI de Neon>` (la misma que usarás en producción).
     - `UPLOADS_DIR=./uploads` (por defecto).

3. **Aplicar migraciones a Neon**
   - Asegúrate de que `FLASK_APP` está configurado para usar la app factory. Por ejemplo en tu entorno:
     - `set FLASK_APP=app:create_app` (Windows) o `export FLASK_APP=app:create_app` (Unix).
   - Ejecuta:
     - `flask db upgrade`

   Alembic (`migrations/env.py`) usa siempre la URL del engine de Flask, así que las migraciones van contra la misma base de datos definida en `SQLALCHEMY_DATABASE_URI` (Neon en este caso).

4. **Seed de datos de ejemplo**
   - Ejecutar:
     - `python -m app.seed`
   - Esto crea un restaurante demo, staff y niveles de recompensa.

5. **Levantar el servidor de desarrollo**
   - Opción 1 (recomendada): `flask run`
   - Opción 2: `python app.py`

   `app.py` usa `create_app()` y respeta `DEBUG` de la configuración, por lo que en local se activa automáticamente si `FLASK_ENV != production` o si `FLASK_DEBUG=1`.

---

## Configuración para Render + Neon

### Build & Start command

- **Build Command**:
  - `pip install -r requirements.txt`
- **Start Command** (Render → Web Service → Start Command):
  - `gunicorn wsgi:app --bind 0.0.0.0:$PORT`

`wsgi.py` expone:

```python
from app import create_app

app = create_app()
```

Por lo tanto `gunicorn wsgi:app` carga la app factory correctamente, y el `--bind 0.0.0.0:$PORT` hace que escuche en el puerto que Render expone.

### Variables de entorno en Render

En la sección **Environment** del servicio en Render, definir al menos:

- `FLASK_ENV=production`
- `SECRET_KEY=<valor fuerte y secreto>`
- `SQLALCHEMY_DATABASE_URI=<URI completa de Neon>`
- `UPLOADS_DIR=/opt/render/project/src/uploads`
- (opcional) `MAX_IMAGE_MB=2`
- (opcional) `RATELIMIT_DEFAULT=100 per minute`

Con `FLASK_ENV=production`, la clase `Config`:

- Exige que `SQLALCHEMY_DATABASE_URI` esté definido (si no, levanta `RuntimeError` y evita caer a SQLite).
- Desactiva el modo debug (`DEBUG=False`).
- Marca las cookies de sesión como `Secure` y `HttpOnly`.

### Migraciones en producción

Hay dos enfoques habituales:

1. **Aplicar migraciones desde local contra Neon** (recomendado para este proyecto):
   - Configura localmente `SQLALCHEMY_DATABASE_URI` apuntando a Neon.
   - Ejecuta `flask db upgrade` desde tu máquina/CI.
   - Render solo ejecuta la app, sin tocar migraciones.

2. **Aplicar migraciones en Render en cada despliegue** (necesitaría script de deploy):
   - Ahora se puede habilitar con la variable `AUTO_MIGRATE=1` en Render.
   - Con `AUTO_MIGRATE=1`, `wsgi.py` ejecuta `flask db upgrade` al arrancar, usando un lock de Postgres para evitar carreras.
   - Esto es útil para prototipos; en producción grande se recomienda el enfoque 1.

Con la configuración actual, el escenario 1 es el esperado.

---

## Manejo de subidas en producción

Código relevante:

- `app/config.py`: `UPLOADS_DIR` (por defecto `./uploads`).
- `app/__init__.py`: crea el directorio en el arranque.
- `app/services/image_service.py`: guarda y optimiza las imágenes.
- `app/routes/uploads.py`: sirve las imágenes vía `/uploads/<filename>`.

Flujo:

1. Al crear la app (`create_app()`), se ejecuta:
   - `os.makedirs(app.config.get("UPLOADS_DIR", "./uploads"), exist_ok=True)`
2. Cuando se sube una imagen (avatar o foto de review):
   - `process_and_save_image()` valida tamaño y tipo, redimensiona si es necesario y guarda el archivo en `UPLOADS_DIR`.
   - Devuelve una URL pública, normalmente `/uploads/<nombre>`.
3. El blueprint `uploads_bp` expone:
   - Ruta `GET /uploads/<filename>` que hace `send_from_directory(UPLOADS_DIR, filename)`.

En Render:

- `UPLOADS_DIR=/opt/render/project/src/uploads` → se crea ese directorio en el sistema de archivos efímero.
- Los archivos no son persistentes entre despliegues, pero se mantienen durante la vida del container, suficiente para un prototipo.

---

## Desplegar una nueva versión en Render

1. **Commit en GitHub**
   - Haz cambios en tu máquina.
   - Ejecuta tests/lint si aplica.
   - `git commit` y `git push` a la rama `main` del repo `COLIMASTER/xinra-app`.

2. **Render detecta el push**
   - Render clona el repo.
   - Ejecuta el **Build Command**: `pip install -r requirements.txt`.
   - Usa la configuración de entorno (`SQLALCHEMY_DATABASE_URI` a Neon, etc.).

3. **Arranque del servicio**
   - Render ejecuta el **Start Command**: `gunicorn wsgi:app --bind 0.0.0.0:$PORT`.
   - Gunicorn carga `wsgi.py`, que crea la app vía `create_app()`.
   - Si falta `SQLALCHEMY_DATABASE_URI` en producción, el arranque falla de forma explícita (evitando usar SQLite por error).

4. **Health check**
   - Render puede usar `/health` como endpoint de comprobación.
   - Ruta implementada en `app/routes/health.py`, registrada en `create_app()`.

---

## Notas sobre logs y observabilidad

- Flask y gunicorn escriben logs en stdout/stderr.
- Render recoge ambos streams automáticamente; no hace falta configurar ficheros de log.
- Para un entorno más avanzado se recomienda:
  - Configurar `LOG_LEVEL` y usar `logging` en puntos críticos.
  - Integrar un servicio tipo Sentry para errores y trazas.

En este proyecto, el mayor impacto está en:

- No exponer tracebacks en producción (se desactiva debug).
- Tener `/health` para checks simples.

---

## Checklist de “producción pequeña”

1. **Base de datos**
   - [x] `SQLALCHEMY_DATABASE_URI` apunta a Neon (no a SQLite).
   - [x] Migraciones aplicadas con `flask db upgrade` contra Neon.

2. **Seguridad**
   - [x] `SECRET_KEY` fuerte y solo en entorno (Render).
   - [x] `FLASK_ENV=production`, `FLASK_DEBUG` desactivado.
   - [x] Cookies de sesión marcadas como `Secure` y `HttpOnly` en producción.

3. **Uploads**
   - [x] `UPLOADS_DIR` fuera de `static/` (p.ej. `/opt/render/project/src/uploads`).
   - [x] Ruta `/uploads/<filename>` activa y funcionando.
   - [x] Límite de tamaño configurado (`MAX_IMAGE_MB`).

4. **Errores y UX**
   - [x] Plantillas personalizadas para 404/500 en `templates/errors/`.
   - [x] Página de salud `/health` para monitorización simple.

5. **CI/CD y workflows**
   - El workflow `azure-webapp.yml` ya no es necesario para Render; se puede:
     - Eliminarlo, o
     - Reemplazarlo por un workflow de tests sencillo (por ejemplo, instalar dependencias y ejecutar `python -m compileall .` o los tests que se añadan).

Con estos puntos, el proyecto queda listo para un entorno de producción pequeño en Render + Neon, con una configuración explícita de base de datos, errores y subidas de archivos.

