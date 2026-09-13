# Migraciones

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

Se empieza con busqueda vectorial exacta. Un indice HNSW se puede agregar cuando
el volumen y las mediciones de latencia lo justifiquen. Cada consulta debe filtrar
organizacion autorizada, modelo de embedding y version publicada. No mezclar
modelos aunque tengan la misma dimension. Para otra dimension crear una migracion.

Instalacion oficial en Windows:
https://github.com/pgvector/pgvector#windows

Las claves foraneas evitan referencias entre organizaciones, pero no sustituyen
la autorizacion de lectura/escritura. La API aun debe implementar autenticacion,
permisos, acceso SQL y transacciones de publicacion (revision de pasos, evidencias,
inmutabilidad de versiones aprobadas y generacion de tutorial/indice).
No se han creado credenciales ni se ha configurado un usuario de ejecucion para
la API; no utilizar la cuenta administradora `postgres` como cuenta de la API.
Los archivos de evidencia se guardaran fuera de PostgreSQL; aqui se guarda su
referencia, hash y metadatos. `users.identity_subject` referencia una identidad
externa; no contiene contrasenas.

Al incorporar Alembic, registrar esta base existente antes de generar cambios;
no volver a crear estas tablas sobre una instalacion que ya tenga la version 001.
