# Catalogo de aprendizaje visual

Actualizado: 2026-09-16. Todas las rutas llevan prefijo `/api/v1`.
24 operaciones HTTP y un WebSocket nuevos; las fichas 01..37 conservan la API previa.

| Metodo | Ruta | Ficha |
| --- | --- | --- |
| GET | `/recordings/capabilities` | [Limites y servicios disponibles](38-capabilities.md) |
| POST | `/learning-sessions/{session_id}/recordings` | [Reservar video](39-reserve-recording.md) |
| GET | `/learning-sessions/{session_id}/recordings` | [Recuperar videos de sesion](40-list-recordings.md) |
| GET | `/recordings/{recording_id}` | [Estado de grabacion](41-get-recording.md) |
| POST | `/recordings/{recording_id}/upload-url` | [URL temporal de subida](42-upload-url.md) |
| POST | `/recordings/{recording_id}/complete` | [Confirmar subida completa](43-complete-recording.md) |
| POST | `/recordings/{recording_id}/process` | [Encolar analisis](44-process-recording.md) |
| POST | `/recordings/{recording_id}/retry` | [Reintentar analisis fallido](45-retry-recording.md) |
| GET | `/recordings/{recording_id}/playback` | [Reproducir video privado](46-playback.md) |
| GET | `/recordings/{recording_id}/report` | [Leer informe](47-get-report.md) |
| PUT | `/recordings/{recording_id}/report` | [Corregir informe](48-edit-report.md) |
| POST | `/recordings/{recording_id}/report/review` | [Revision humana e indexacion](49-review-report.md) |
| POST | `/recordings/{recording_id}/report/regenerate` | [Regenerar con respuestas](50-regenerate-report.md) |
| POST | `/recordings/{recording_id}/procedure` | [Convertir a procedimiento](51-convert-report.md) |
| GET | `/recordings/{recording_id}/upload-status` | [Consultar bloques](52-upload-status.md) |
| POST | `/recordings/{recording_id}/commit-blocks` | [Confirmar bloques reanudables](53-commit-blocks.md) |
| GET | `/recordings/{recording_id}/report/history` | [Historial de revisiones](54-report-history.md) |
| GET | `/recordings/{recording_id}/transcript` | [Transcripcion y consentimiento](55-transcript.md) |
| GET | `/learning-sessions/{session_id}/jobs` | [Recuperar trabajos por sesion](56-session-jobs.md) |
| GET | `/learning-sessions/{session_id}/agent/messages` | [Recuperar conversacion](57-agent-messages.md) |
| GET | `/recordings/{recording_id}/flow` | [Grafico del proceso](58-recording-flow.md) |
| POST | `/recordings/{recording_id}/index` | [Indexar o reintentar indice](59-index-recording.md) |
| GET | `/recordings/{recording_id}/index` | [Comprobar indice vectorial](60-index-status.md) |
| POST | `/recordings/search` | [Busqueda semantica de videos](61-search-recordings.md) |
| WS | `/learning-sessions/{session_id}/agent/live` | [Observacion y conversacion en vivo](62-agent-live.md) |
