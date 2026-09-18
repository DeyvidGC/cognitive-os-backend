# Migraciones

2026-09-17: `008_job_progress.sql` agrega stage/progress_percent a los trabajos.
Aplicada en cognitive local despues de verificarla en PostgreSQL aislado.

Migraciones SQL manuales, en orden, desde Query Tool conectado a `cognitive`.
Cada archivo tiene su propia transaccion. Ejecutar cada version una sola vez;
el registro `cognitive.schema_migrations` indica las versiones aplicadas.
Si una ejecucion falla, ejecutar `ROLLBACK` antes de corregirla y reintentar.

- `001_initial.sql`: crea el esquema `cognitive`, 16 tablas de negocio y el
  registro de migraciones. Incluye claves foraneas por organizacion, restricciones
  de estados, idempotencia de eventos/trabajos y busqueda textual en espanol.
- `002_pgvector.sql`: requiere instalar previamente pgvector en el servidor.
  Agrega `chunk_embeddings` con vectores de 1536 dimensiones y nombre del modelo.
  No genera embeddings; la API debera generarlos a partir de `knowledge_chunks`.
- `004_local_auth.sql`: credenciales locales y tokens revocables. Requiere 001,
  no requiere 002. El archivo `003_Query` es una consulta, no una migracion.
- `005_recordings.sql`: grabaciones Azure, informes y trabajos de analisis visual.
- `006_interactive_learning.sql`: consentimiento de audio, hash, historial de
  informes, evidencia de video por paso y conversacion del agente.
- `007_recording_vectors.sql`: requiere 002 y 006; vectores de informes aprobados
  y trabajos index_recording. Modelos de embedding distintos no se mezclan.

Estado 2026-09-16: 001, 002, 004, 005, 006 y 007 aplicadas en cognitive local.
La generacion/vectorizacion se ejecuta con workers separados, no al migrar.

Se empieza con busqueda vectorial exacta. Un indice HNSW se puede agregar cuando
el volumen y las mediciones de latencia lo justifiquen. Cada consulta debe filtrar
organizacion autorizada, modelo de embedding y version publicada. No mezclar
modelos aunque tengan la misma dimension. Para otra dimension crear una migracion.

Instalacion oficial en Windows:
https://github.com/pgvector/pgvector#windows

Las claves foraneas evitan referencias entre organizaciones, pero no sustituyen
la autorizacion de lectura/escritura. La API implementa autenticacion local,
permisos por membresia y publicacion manual. Workers y vectores de video estan
implementados; RLS y un rol DB productivo de minimo privilegio siguen pendientes.
No se han creado credenciales ni se ha configurado un usuario de ejecucion para
la API; no utilizar la cuenta administradora `postgres` como cuenta de la API.
Los archivos de evidencia se guardaran fuera de PostgreSQL; aqui se guarda su
referencia, hash y metadatos. `users.identity_subject` identifica al usuario;
las contrasenas se guardan como hashes en local_credentials, nunca como texto plano.

Al incorporar Alembic, registrar esta base existente antes de generar cambios;
no volver a crear estas tablas sobre una instalacion que ya tenga la version 001.
