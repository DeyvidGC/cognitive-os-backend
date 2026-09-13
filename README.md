# Cognitive OS API

Base modular en FastAPI para capturar procesos de negocio y convertirlos
en conocimiento revisable, tutoriales y consultas con RAG.

## Desarrollo local

Python 3.12 o superior. Desde la raiz del proyecto en PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e '.[dev]'
.venv/Scripts/python.exe -m uvicorn cognitive_os.main:app --reload
```

Documentacion interactiva: http://127.0.0.1:8000/docs
Estado del proceso: `GET /api/v1/health` (no comprueba servicios externos).
Se conservan `/` y `/hello/{name}` por compatibilidad.

La configuracion lee variables con prefijo `COGNITIVE_` y un archivo `.env`
opcional. Las variables disponibles estan en `.env.example`.

## Estructura

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
migrations/        Futuras migraciones
tests/             Pruebas
docs/              Arquitectura y alcance del producto
```

Las carpetas de negocio y adaptadores son puntos de extension. Persistencia,
autenticacion, sesiones, captura, IA y RAG aun no estan implementados.
La siguiente entrega es persistencia y acceso para las sesiones de aprendizaje.

## Pruebas

```powershell
.venv/Scripts/python.exe -m pytest
```

## Ramas

`main` conserva la base estable y `develop` es la rama de desarrollo.
`master` se renombro a `main`, conservando su historial.
