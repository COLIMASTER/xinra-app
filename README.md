Que es Xigma Tips
Xigma Tips es una app web para que un restaurante reciba propinas y feedback desde un enlace/QR. Es mobile‑first y funciona con Python + Flask (HTML Jinja).

Paneles incluidos
- Panel de usuarios ("Mi panel"): perfil, progreso de niveles/XP, restaurantes valorados, historico de propinas y resenas.
- Panel de administrador ("Admin"): metricas (hoy/semana/mes), graficas, ranking de trabajadores, resenas recientes y una vista de pagos (mock) para enviar propinas a trabajadores.

Como se guardan los datos
- Desarrollo: por defecto usa SQLite (archivo dev.db) para simplificar.
- Produccion: usa PostgreSQL. Los modelos estan listos para migraciones con Flask‑Migrate/Alembic.
- Archivos (fotos): en desarrollo se guardan en la carpeta configurada (por defecto ./uploads, servida via /uploads). En produccion lo normal es S3/GCS.
- Rate limiting/sesion: Flask‑Limiter funciona en memoria en desarrollo. En produccion se recomienda Redis para rate‑limits y sesiones.

Requisitos
- Python 3.10+
- pip
- (Produccion) PostgreSQL y Redis

Instalacion paso a paso (desarrollo)
1) Crear entorno virtual y dependencias
   cd flask_app
   python -m venv .venv
   .\\.venv\\Scripts\\activate   # Windows
   # source .venv/bin/activate      # macOS/Linux
   pip install -r requirements.txt

2) Variables de entorno
   Copia .env.example a .env y ajusta si quieres usar Postgres.
   Por defecto: SQLite en dev.db y SECRET_KEY de desarrollo.

3) Base de datos y seed
   flask db init        # solo la primera vez del proyecto
   flask db migrate -m "init"
   flask db upgrade
   python -m app.seed   # crea restaurante demo y usuarios

4) Ejecutar
   python app.py

Rutas utiles
- Publico: /r/cafe-luna (pagina de propinas y feedback)
- Salud: /health
- Mi panel (usuario): /me/profile
- Admin (restaurante): /dashboard/restaurant, /dashboard/payouts y /dashboard/coupons

Roles y acceso
- Usuario invitado: puede dejar propinas/resenas sin registrarse (se usa cookie de dispositivo).
- Usuario registrado: acumula XP y niveles; "Mi panel" muestra progreso y actividad.
- Admin/Manager: acceso a "Admin"; la relacion se guarda en Membership por cada restaurante.

Como funciona internamente (resumen tecnico)
- app/models.py define las tablas (User, Restaurant, Staff —con bio—, Tip, Review, Transfer, etc.).
- app/routes/public.py sirve la UX publica: propina (metodo simulado), feedback con estrellas + foto.
- app/routes/auth.py gestiona login/registro y "Mi panel".
- app/routes/dashboard.py ofrece KPIs, rankings, graficas y pagos mock.
- app/utils y app/services agrupan utilidades (seguridad, device cookies) y logica de negocio.
- Flask‑WTF valida formularios y protege con CSRF. Flask‑Limiter aplica limites.

Preparacion para comercializar
1) Infraestructura
   - Base de datos: PostgreSQL gestionado (pgBouncer opcional) y migraciones con Alembic.
   - Archivos: S3/GCS para fotos; configura credenciales por ENV.
   - Rate‑limit/sesion: Redis administrado.
   - Servidor: gunicorn + reverse proxy (Nginx) o plataforma PaaS (Render/Fly/Heroku).
   - Entorno: variables en .env (SECRET_KEY, SQLALCHEMY_DATABASE_URI, REDIS_URL, UPLOADS_DIR/S3 config).

2) Despliegue
   - Instala dependencias (pip install -r requirements.txt).
   - Apunta SQLALCHEMY_DATABASE_URI a Postgres.
   - flask db upgrade (aplica migraciones).
   - Lanza gunicorn: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app.
   - Coloca Nginx delante (TLS, compresion, caching estatico).

3) Observabilidad y tareas
   - Logs estructurados (stdout/stderr) y monitoreo (Sentry/ELK/CloudWatch).
   - Cola de tareas (RQ/Celery) para procesar imagenes y tareas asincronas.

4) Seguridad y cumplimiento
   - CSRF y sesiones seguras (SESSION_COOKIE_SECURE en prod).
   - Limite de subida (MAX_IMAGE_MB) y validacion de tipo.
   - Politicas de privacidad y manejo de datos personales.

Onboarding para otra empresa
1) Clonar el repo y seguir "Instalacion paso a paso (desarrollo)".
2) Ejecutar python -m app.seed para generar datos demo.
3) Crear un usuario admin propio y asignar Membership al restaurante.
4) Ajustar branding (logo, colores en static/css/custom.css) y textos.
5) Para produccion, aplicar "Preparacion para comercializar".

FAQ
- No veo "Admin" en el menu → tu usuario no tiene rol admin/manager en Membership.
- No aparecen graficas → Chart.js debe cargar; ya se incluye con defer. Si personalizas plantillas, asegura que el JS de Chart corre despues de la carga.
- Donde estan los archivos subidos → en ./uploads (desarrollo) accesible por /uploads. En produccion usa S3/GCS y configura los ENV.

Notas nuevas
- Cupones: administra cupones por restaurante en `/dashboard/coupons`. Los usuarios pueden canjearlos desde su panel si alcanzan el XP requerido.
- Migraciones: tras actualizar modelos (Coupons), ejecuta `flask db migrate -m "coupons" && flask db upgrade`. Para datos de ejemplo, `python -m app.seed`.
