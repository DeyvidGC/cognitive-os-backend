# Mejoras del frontend: orden recomendado

Fecha: 2026-09-16. Repositorio revisado: Cognitive-Os en el escritorio del usuario.
El backend de esta entrega ya expone los contratos; la unica modificacion de frontend
realizada aqui fue la correccion de reproduccion en ScreenStudio.tsx.

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

## Prueba de aceptacion conjunta

Grabar con audio > pausar > terminar > reproducir local > subir > interrumpir red >
reanudar > reproducir remoto y buscar segundo > analizar > responder pregunta >
regenerar > revisar > aprobar > visualizar grafo > convertir/publicar > buscar fuente.

Repetir recargando pagina durante subida/procesamiento; probar token y SAS vencidos,
worker detenido y acceso de otra organizacion. No declarar esta prueba completada
hasta ejecutarla con las claves reales y los componentes integrados.

[Contratos, payloads y comandos](06-aprendizaje-visual.md) |
[Catalogo por endpoint](../endpoints/visual-catalogo.md).
