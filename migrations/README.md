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
- `008_job_progress.sql`: requiere 005; agrega `stage` y `progress_percent` a
  `jobs`. La API las mapea siempre, asi que sin esta migracion cualquier consulta
  de trabajos falla con 503 `Database unavailable or migrations missing`.
- `009_periodic_learning.sql`: requiere 001 y 005; agrega `procedure_id` a
  `learning_sessions` y `title` y `origin` a `recordings`. Es aditiva y conserva
  los datos. Sin ella, listar sesiones falla con 503 aunque el resto de la API
  responda con normalidad, porque el modelo ya mapea esas columnas.
- `010_realtime_voice.sql`: requiere 001 y 006; agrega `realtime_voice_sessions`
  (una sesion de voz en vivo activa por `learning_session`, via indice unico
  parcial) y el tipo de evento `realtime_voice_transcript` en `session_events`,
  separado del `transcript` que ya podia enviar el cliente. Sin ella, el agente
  de voz en vivo no puede persistir sesiones ni transcripcion.
- `011_knowledge_consolidation.sql`: requiere 007; agrega `status` y
  `superseded_by` a `recording_vectors`. Permite que una grabacion nueva de un
  procedimiento ya indexado marque como `superseded` los fragmentos antiguos que
  actualiza, en vez de solo acumular vectores. Aditiva: las filas existentes
  quedan `active` por defecto. Ver [modelo curador](../docs/seguimiento/guias/06-aprendizaje-visual.md).
- `012_knowledge_gaps.sql`: requiere 002 y 007; agrega `knowledge_gaps`, una
  pregunta del chatbot que el conocimiento publicado no pudo responder. Se
  deduplica por similitud de embedding: repreguntar lo mismo con otras palabras
  incrementa `asked_count` de la misma fila en vez de crear otra.
- `013_chat_queries.sql`: requiere 001 y 012; agrega `chat_queries`, un registro
  de cada pregunta al chatbot (respondida o no) para que el dashboard de uso
  calcule conteos, volumen diario y temas mas preguntados sin recalcularlos
  desde `knowledge_gaps`, que solo guarda las no respondidas.
- `014_policy_analyzer.sql`: requiere 002 y 013; agrega `policy_documents` (con
  su propia maquina de estados uploading/queued/processing/ready/failed, sin
  usar `cognitive.jobs`) y `policy_vectors` (vectores por clausula). Agrega
  `policy_id` a `chat_queries` para que el dashboard de uso mezcle preguntas
  del chatbot de conocimiento y del analizador de polizas.
- `015_change_proposals.sql`: requiere 001; agrega `change_proposals`, una
  solicitud de cambio en lenguaje natural sobre una version publicada.
  Aplicarla nunca modifica la version publicada: crea una nueva version
  `draft` (version_number+1) que igual debe pasar por submit/approve/publish.
- `016_platform_staff.sql`: requiere 001; agrega `users.is_platform_staff`
  (default false). Solo estos usuarios pueden usar `/master/*` para comparar
  conocimiento y uso entre organizaciones, saltandose a proposito el chequeo
  de membresia por organizacion que exige el resto de la API.
- `017_policy_retire.sql`: requiere 014; agrega `'retired'` a los estados
  validos de `policy_documents`. Retirar una poliza la saca de busqueda y
  listados sin borrarla: esta base no tiene endpoints DELETE en ningun lado.
- `018_change_proposal_kinds.sql`: requiere 015; agrega `kind`
  (insert/edit/delete, default `insert`) y `step_position` a
  `change_proposals`. Antes solo se podia insertar un paso; ahora tambien se
  puede pedir editar el texto de un paso existente o eliminarlo.

Las dieciocho son obligatorias: `cognitive_os.infrastructure.database.migrations`
las declara en `REQUIRED_MIGRATIONS` y `GET /api/v1/health/ready` nombra las que
falten. Al agregar una migracion, agregarla tambien a esa tupla y a
`scripts/test_postgres.ps1`.

Estado 2026-09-18: 001, 002, 004, 005, 006, 007, 008 y 009 aplicadas en cognitive local;
010 pendiente de aplicar.
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
