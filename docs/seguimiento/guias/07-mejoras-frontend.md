# Mejoras del frontend: orden recomendado

Fecha: 2026-09-18. Repositorio revisado: Cognitive-Os en el escritorio del usuario.
El backend de esta entrega ya expone los contratos; la unica modificacion de frontend
realizada aqui fue la correccion de reproduccion en ScreenStudio.tsx.

Actualizacion 2026-09-18: se agrego el backend del agente en vivo con voz
bidireccional (`/agent/live-voice`, seccion 7 mas abajo). No se toco ningun
componente de frontend para implementarlo; sigue pendiente por completo.

## 1. Sesion recuperable

- Al entrar a una sesion recuperar grabacion, jobs y mensajes del agente.
- Mostrar por separado subida, analisis e indexacion; no usar un unico spinner.
- No repetir reserva ni process al recargar: primero consultar estado remoto.
- Detener polling al finalizar, salir de la vista o recibir 401; backoff ante errores.
- Aun sin IA/Azure, permitir notas y explicar servicio no configurado sin falso exito.

Componentes: SessionMedia, RecordingUploadPanel, JobProgress y recordings.ts.

## 2. Agente en vivo

- Conectar WebSocket solo con consentimiento y sesion capturando; proxy Vite con ws:true.
- Primera trama auth; nunca API key ni token en query string.
- Captura puntual JPEG/PNG reducida, base64 sin prefijo data, no enviar cada frame.
- Un turno pendiente a la vez, intervalo minimo informado por ready y UUID estable.
- Mostrar observacion, respuesta y preguntas como partes distintas; recuperar historial.
- Manejar 401/403 cerrando conexion; 409/429/503 ofreciendo reintento contextual.
- Detener envios al pausar/cerrar captura; no reconectar infinitamente una sesion terminada.

Componentes: ScreenStudio y AgentConversation. No existe voz bidireccional en este socket.

## 3. Audio y reproduccion

- Reservar con audio_consent solo cuando el usuario haya autorizado audio.
- Permitir inspeccionar transcripcion; mostrar por que no se analizo si falta audio/consentimiento.
- Mantener preview local separado del elemento en vivo (ya corregido y probado).
- Para video guardado usar playback.url como src, sin pasar por el cliente JSON.
- Ante SAS vencido pedir otra URL, esperar loadedmetadata y restaurar currentTime.
- Diferenciar fallo de red/autorizacion y MediaError de codec; ofrecer descarga como alternativa.
- Probar WebM/MP4 reales y controles de seek en los navegadores objetivo.

Componentes: SessionMedia y ScreenStudio. El servidor no convierte cualquier codec
a uno universal; la compatibilidad remota debe verificarse con Azure y archivos reales.

## 4. Informe revisable

- Mostrar resumen, instrucciones, incertidumbres, preguntas y fuente de cada paso.
- Contestar aclaraciones con las rutas existentes, luego regenerar usando revision actual.
- Refrescar ante 409 y conservar texto local para no perder cambios del usuario.
- Comparar revisiones desde report/history; deshabilitar edicion despues de aprobacion.
- Aprobar y convertir son acciones distintas; despues abrir la version del procedimiento.
- Publicar solo por el circuito submit/approve/publish y con el rol autorizado.

Componente: RecordingReport. No sustituir la confirmacion HTTP por un estado optimista
de aprobado/publicado; la API es la fuente de verdad.

## 5. Grafico navegable

- Consumir GET /recordings/{id}/flow; usar nodes y edges, no pedir un dibujo al modelo.
- Renderizar inicio/pasos/fin; marcar pendiente/aprobado y revision visible.
- Al seleccionar un paso mostrar resultado esperado, fuentes y segundos del video.
- Saltar a frames[].timestamp_ms / 1000 en el reproductor; renovar SAS si hace falta.
- Ajustar layout/altura al texto, zoom, encajar y alternativa de lista para movil/accesibilidad.
- Renderizar etiquetas como texto; sanitizar Markdown, nunca insertar HTML de la IA.

El contrato tiene posiciones iniciales verticales, pero el frontend debe recalcularlas
si la longitud del texto cambia. No mostrar rombos de decisiones que no existen en los datos.

## 6. Subida resistente a cortes y busqueda

- Calcular SHA-256, recuperar upload-status y subir solamente bloques pendientes.
- Validar que el archivo seleccionado coincide con el hash antes de reanudar.
- Guardar identificadores de reserva por sesion; no guardar SAS ni claves en almacenamiento local.
- Cerrar con commit-blocks, luego process. Confirmaciones se pueden repetir.
- Mostrar indice pendiente/listo/fallido sin bloquear reproduccion del video.
- Buscador POST /recordings/search: presentar fragmento, fuente, video y revision;
  score es similitud, no porcentaje de certeza. Todavia no es un chat RAG.

## 7. Agente por voz en vivo (nuevo, no implementado en frontend)

Backend listo en `WS /api/v1/learning-sessions/{session_id}/agent/live-voice`
([ficha completa](../endpoints/63-agent-live-voice.md)). Es un socket distinto
de `/agent/live`: streaming continuo, no turnos, y el usuario habla y escucha
en vez de escribir. Falta todo el lado de frontend.

### Conexion y ciclo de vida

- Conectar solo con consentimiento explicito de audio y con la sesion en
  `capturing`; primera trama `{type:"auth", token, organization_id, consent:true}`,
  igual que `/agent/live`. Nunca token en query string ni API key de OpenAI en
  el cliente (el backend nunca la expone; no hay nada que guardar del lado del
  navegador para hablar con OpenAI).
- Esperar `{"type":"ready", audio_input, audio_output, observation_interval_seconds,
  session_max_seconds, ...}` antes de abrir microfono o mandar capturas.
- Solo puede haber una llamada de voz activa por sesion. Si la conexion
  responde `{"type":"error","status":409}`, no reintentar automaticamente:
  avisar al usuario que ya hay otra llamada abierta (otra pestana/dispositivo).
- Manejar `{"type":"session.ending","reason":...}` cerrando microfono y UI de
  llamada de inmediato; mostrar el motivo (`max_duration`, `session_status_changed`,
  `client_disconnect`, `error`) en vez de un error generico.
- Mandar `{"type":"end"}` y cerrar el socket al colgar, salir de la vista
  o cerrar la sesion. Cambiar de pestana o aplicacion mantiene la llamada,
  el microfono y las capturas (requisito actualizado el 2026-09-19).
  No reconectar solo despues de un cierre limpio o `max_duration`.
- Errores `401`/`403` cierran la conexion como en `/agent/live`; no reintentar
  con el mismo token.

### Audio: microfono y reproduccion

- Capturar con `getUserMedia({audio: true})` solo tras consentimiento explicito
  y visible (checkbox/boton, no implicito por compartir pantalla).
- Codificar a PCM16 crudo (no WAV/Opus/WebM) en trozos pequenos —
  `AudioWorkletNode` es preferible a `ScriptProcessorNode` (deprecado) — y
  mandarlos como **tramas binarias** WS, respetando el tope de tamano por
  trozo que informa el backend (`realtime_audio_chunk_max_bytes`, 32 KB por
  defecto). No envolver el audio en JSON ni base64.
- El audio de respuesta (TTS) llega tambien en tramas **binarias** PCM16;
  reproducir con Web Audio API (`AudioContext.decodeAudioData` no aplica a PCM
  crudo: usar `createBuffer` + `copyToChannel` o un `AudioWorklet` de
  reproduccion en streaming). Cortar la reproduccion inmediatamente al recibir
  `session.ending` o al colgar.
- Mostrar un indicador de "escuchando"/"hablando" basado en si se estan
  mandando o reproduciendo chunks, no solo en el estado de conexion del socket.

### Capturas de pantalla

- Reenviar la misma captura periodica puntual que ya usa `ScreenStudio` para
  `/agent/live` (mismo formato JPEG/PNG, base64 sin prefijo `data:`, hasta
  512 KB), pero como `{"type":"frame","image_base64":"..."}` en el socket de
  voz, con la cadencia que indico `ready.observation_interval_seconds`
  (15s por defecto). No mandar cada frame de un stream de video.

### Preguntas proactivas

- `{"type":"clarification.created","clarification_id":"UUID","question":"..."}`
  puede llegar en cualquier momento, sin que el usuario haya preguntado nada:
  necesita una UI propia (notificacion/banner sobre la llamada), distinta de
  como `AgentConversation` muestra las respuestas de `/agent/live`.
- Responder con `{"type":"clarification_answer","clarification_id":"UUID","text":"..."}`
  cuando el usuario conteste por texto; si contesta por voz, el backend ya la
  transcribe y la guarda como conversacion, pero la `Clarification` en si solo
  se resuelve mandando ese mensaje explicito (no basta con hablar la respuesta).
- Reutilizar el listado de `GET /learning-sessions/{id}/clarifications` para
  mostrar el historial completo de preguntas, incluidas las que hizo la voz.

### Que no hace falta construir

- No hay que generar ni administrar tokens efimeros de OpenAI: el backend
  media toda la conexion, el frontend solo habla con nuestro propio WebSocket.
- No hay que decodificar function calls ni tool calls de OpenAI: el frontend
  solo ve `clarification.created`, ya resuelto por el backend.
- No hay que grabar ni subir el video por este canal: si se quiere que la
  llamada de voz alimente el informe final, la grabacion de pantalla sigue
  siendo el flujo de video normal (`RecordingUploadPanel`) en paralelo; el
  backend ya conecta la transcripcion de voz con ese analisis solo.

### Prueba de aceptacion de esta seccion

Abrir sesion en captura > conectar `/agent/live-voice` > autorizar microfono >
hablar y escuchar respuesta > compartir pantalla y verificar que llegan
capturas periodicas > provocar una pregunta proactiva y responderla > intentar
abrir una segunda llamada de voz en otra pestana y ver el 409 > colgar y
verificar que el microfono se apaga > dejar pasar el limite de duracion (o
bajarlo en settings para la prueba) y verificar `session.ending` con
`max_duration` > terminar la sesion y confirmar que el informe final (si hubo
video grabado en paralelo) trae la transcripcion de voz sin re-transcribir el
audio del video.

## Prueba de aceptacion conjunta

Grabar con audio > pausar > terminar > reproducir local > subir > interrumpir red >
reanudar > reproducir remoto y buscar segundo > analizar > responder pregunta >
regenerar > revisar > aprobar > visualizar grafo > convertir/publicar > buscar fuente.

Repetir recargando pagina durante subida/procesamiento; probar token y SAS vencidos,
worker detenido y acceso de otra organizacion. No declarar esta prueba completada
hasta ejecutarla con las claves reales y los componentes integrados.

[Contratos, payloads y comandos](06-aprendizaje-visual.md) |
[Catalogo por endpoint](../endpoints/visual-catalogo.md).
