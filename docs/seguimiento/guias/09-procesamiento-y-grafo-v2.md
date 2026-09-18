# Procesamiento automatico y grafo v2

Actualizado: 2026-09-17. Esta guia reemplaza las indicaciones anteriores de workers
solo manuales y grafo exclusivamente secuencial para el entorno local actual.

## Causa de Procesar video sin avance

La API creaba correctamente un job analyze_recording, pero no habia worker activo.
Se encontro pending con cero intentos. Las claves por si solas no inician workers.

Ahora .env y .env.example incluyen COGNITIVE_EMBEDDED_WORKERS=true: al iniciar
main:app desde PyCharm, el lifespan inicia procesos de consolidacion, analisis de
video e indexacion. PostgreSQL conserva la cola y evita tomar dos veces el mismo
trabajo mediante leases. No se ejecuta el analisis dentro de la peticion HTTP.

En produccion usar false y workers dedicados. No multiplicar los workers integrados
por cada replica HTTP sin planificar recursos. Al cerrar la API se solicita parada;
despues de cinco segundos se terminan los hijos que sigan ocupados. Un trabajo
interrumpido queda recuperable cuando expire su lease, hasta 900 segundos en video.
Evitar --reload mientras se analiza un video: un cambio de codigo reinicia workers.

## Estado y errores para el frontend

Migracion 008_job_progress aplicada a cognitive. GET /jobs/{id} y jobs por sesion
ahora agregan stage, progress_percent, last_error, available_at y max_attempts.

Etapas: queued, starting, downloading, extracting, transcribing, analyzing,
saving, embedding, retry_wait, completed, failed. El porcentaje expresa hitos del
pipeline, no porcentaje de tokens ni prediccion de tiempo restante.

Errores sanitizados distinguen clave invalida, modelo sin acceso, cuota agotada,
rate limit, conexion, solicitud rechazada, decodificacion e integridad del archivo.
No se devuelven mensajes crudos del SDK ni URLs SAS. Fallos definitivos requieren
corregir configuracion y reintentar; los temporales usan el backoff de la cola.

GET /recordings/capabilities agrega ai_configured, worker_mode y local_workers.
Un proceso vivo no demuestra que un proveedor este sano; consultar tambien el job.
El frontend local ya muestra las etapas y errores en SessionJobs y JobProgress.

## Analisis mejorado

- Intervalo configurable, ahora cinco segundos por defecto, mas el ultimo fotograma.
- Hasta 122 muestras dentro del limite de diez minutos; mayor detalle implica costo.
- Prompt visual-report-v2: acciones concretas, resultado esperado separado de exito
  observado, preguntas ante vacios, sin reproducir credenciales ni inventar evidencia.
- Requisitos previos, reglas y excepciones llevan frame_indices/text_sources.
- Las condiciones alternativas solo se aceptan cuando los pasos siguen siendo
  alcanzables, no hay ciclos y los destinos existen.
- Los hechos nuevos se conservan en la conversion a tutorial y en los embeddings.

Los campos nuevos de ReportContent son listas opcionales con valor vacio por defecto:
prerequisites, business_rules, exceptions. Cada elemento contiene text, frame_indices
y text_sources. Cada instruccion agrega alternatives:

```json
[
  {"condition": "Faltan datos", "target_step": 2},
  {"condition": "Los datos estan completos", "target_step": null}
]
```

target_step usa numeracion desde uno; null significa Fin. Una decision requiere
al menos dos condiciones distintas y solo admite destinos posteriores. Bucles de
proceso no se modelan en esta version. Si no hay evidencia de una decision, la
instruccion mantiene alternatives vacio. No se crean ramas decorativas.

## Contrato de grafo

GET /recordings/{id}/flow devuelve schema_version:2, kind:sequence|conditional,
nodes, edges, revision, review_status, prerequisites, business_rules y exceptions.
Sin instrucciones devuelve nodos/aristas vacios y empty_reason:insufficient_evidence.

Se conservan id/type/position/data para compatibilidad. Cada nodo de paso agrega
step_number, node_kind:action|decision, origin, evidence_start_ms, evidence_end_ms
y suggested_height. Las marcas de tiempo describen evidencia muestreada, no la
duracion exacta de una accion. expected_result tampoco certifica que sucedio.

Las aristas condicionales incluyen label. El frontend debe usar source/target,
no asumir que todos los nodos estan conectados consecutivamente. Se actualizaron
las etiquetas de condiciones y la lectura de hechos en el frontend existente;
el layout visual de ramas lado a lado y el editor completo de hechos pueden
evolucionar sin cambiar los IDs del contrato. Al cambiar revision refrescar el grafo.

## Verificacion real

- Credenciales de Azure y acceso a los tres modelos verificados sin mostrar claves.
- Jobs reales de analisis e indexacion completados, un intento, sin error.
- Informe aprobado existente: 10 instrucciones, 35 fotogramas, audio transcrito.
- Grafo de ese informe: 12 nodos y 11 aristas; 19 fragmentos en recording_vectors.
- Azure snapshot responde 206 a Range y MIME video/webm con inline.
- Se agrego CORS para https://cognitive-os-frontend.vercel.app conservando la regla
  local. Verificados GET 206 y preflight PUT 200 con origen permitido.
- 55 pruebas backend en PostgreSQL aislado, 23 frontend y build TypeScript/Vite.
- Vista desktop/movil y salto a segundo del video comprobados con fixture sintetico
  en Edge; no hubo desbordamiento horizontal.

Los informes aprobados/rechazados observados son decisiones del usuario; el agente
no los aprobo ni modifico para hacer pasar una prueba. No se guardaron keys en docs.

## Que debes hacer

Publicar los cambios del repositorio frontend en Vercel. Las credenciales actuales
alcanzan para este flujo; no hace falta otra key. Mantener API y workers/tunel activos
cuando uses el frontend desplegado. La instancia de API que el usuario abrio durante
la verificacion no fue detenida por esta tarea.

Pendientes de producto: editor visual de ramas con layout real, chat RAG redactado
con citas, retencion/borrado coordinado y pruebas de carga/limites por organizacion.
No se declara el producto completo listo para produccion.
