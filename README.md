# Cognitive OS API

Base modular en FastAPI para capturar procesos de negocio y convertirlos
en conocimiento revisable, tutoriales y consultas con RAG.

## Desarrollo local

Guia explicada: [documentacion y seguimiento](docs/seguimiento/README.md).
Plan del producto: [requisitos, backlog y sprints](docs/seguimiento/planificacion/README.md).

En PyCharm, seleccionar **Cognitive API (Uvicorn)**, configuracion compartida en
`.run/`. Utiliza `.venv` y un nombre de aplicacion explicito. La configuracion
antigua de tipo FastAPI puede fallar al detectar el `app` importado en `main.py`.
Ver [solucion de arranque](docs/seguimiento/guias/04-arranque.md).

Python 3.12 o superior. Desde la raiz del proyecto en PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e '.[dev]'
.venv/Scripts/python.exe -m uvicorn main:app --reload
```

Documentacion interactiva: http://127.0.0.1:8000/docs
Las ejecuciones locales usan el puerto 8000. El asistente detiene su ejecucion
al terminar las comprobaciones para dejar el puerto libre para PyCharm.
Estado del proceso: `GET /api/v1/health` (no comprueba servicios externos).
Estado de la base: `GET /api/v1/health/ready`, que responde 200 cuando la base
responde y tiene todas las migraciones, y 503 nombrando las que falten. Es la
primera comprobacion ante un 503 `Database unavailable or migrations missing`.
Se conservan `/` y `/hello/{name}` por compatibilidad.

La configuracion lee variables con prefijo `COGNITIVE_` y un archivo `.env`
opcional. Las variables disponibles estan en `.env.example`.

## Estructura

Nuevo flujo visual: [pantalla, audio, agente, informes y reanudacion](docs/seguimiento/guias/06-aprendizaje-visual.md).

```text
src/cognitive_os/
  main.py          Factoria y aplicacion FastAPI
  api/v1/endpoints Rutas HTTP versionadas
  core/            Configuracion
  schemas/         Contratos de entrada y salida
  domain/          Entidades y reglas del negocio
  application/     Casos de uso
  infrastructure/
    database/      Persistencia
    storage/       Archivos de evidencia
    ai/            Modelos y recuperacion
  workers/         Procesamiento en segundo plano
migrations/        Migraciones SQL versionadas
tests/             Pruebas
docs/              Arquitectura y alcance del producto
```

Implementado: autenticacion local, modelos SQLAlchemy, sesiones, eventos,
capturas de imagen, aclaraciones, procedimientos versionados, revision, tutoriales
Markdown y busqueda textual por organizacion. Ver [docs/api.md](docs/api.md).

La API no crea tablas al arrancar. Sobre una base nueva hay que ejecutar, en este
orden, las siete migraciones:

```text
001_initial  002_pgvector  004_local_auth  005_recordings
006_interactive_learning  007_recording_vectors  008_job_progress
```

Ninguna es opcional. `002_pgvector` requiere instalar pgvector en el servidor y
`007_recording_vectors` no se puede aplicar sin ella. Saltarse `007` u `008` deja
la tabla `jobs` sin las columnas y el check que usa la API, y cualquier peticion
que cree o consulte trabajos responde 503 `Database unavailable or migrations
missing`. `003_Query` es una consulta local, no una migracion.

Sobre una base que ya tenga una version anterior, aplicar solo las que falten;
`GET /api/v1/health/ready` las lista por nombre. Detalle de cada archivo en
[migrations/README.md](migrations/README.md).

Configurar `COGNITIVE_DATABASE_URL` en `.env` segun `.env.example`, usando un usuario
con acceso al esquema `cognitive`. Configurar `COGNITIVE_REGISTRATION_ENABLED=true`
para habilitar altas. Sin URL los recursos de datos responden 503; documentacion
y health siguen disponibles. No se usa una base alternativa ni datos en memoria.

Cada registro crea una organizacion y su propietario. Invitaciones, recuperacion
de contrasenas, verificacion de correo y administracion de miembros quedan pendientes.

El cierre de sesion guarda un trabajo pending. El worker con LangGraph genera
borradores desde texto con OpenAI; requiere clave local y proceso separado.
Ver [como ejecutarlo](docs/seguimiento/guias/05-orquestacion.md).
Embeddings, busqueda vectorial, chat RAG y voz quedan pendientes; ver
[docs/orquestacion.md](docs/orquestacion.md).

## Pruebas

```powershell
.venv/Scripts/python.exe -m pytest
```

Las pruebas de integracion requieren `COGNITIVE_TEST_DATABASE_URL` apuntando a un
PostgreSQL de pruebas con pgvector y las siete migraciones aplicadas. Generan
datos con UUID nuevos; no usar una base con datos reales. Sin esa variable se
omiten dichas pruebas y `pytest` termina en verde sin haberlas ejecutado, asi que
conviene comprobar que el resumen no diga `skipped`.
En Windows con PostgreSQL 18, `scripts/test_postgres.ps1` prepara y detiene una
instancia temporal aislada automaticamente, con las migraciones ya aplicadas.
Las migraciones exigen que la base se llame `cognitive`, tambien la de pruebas.

## Ramas

`main` conserva la base estable y `develop` es la rama de desarrollo.
`master` se renombro a `main`, conservando su historial.
