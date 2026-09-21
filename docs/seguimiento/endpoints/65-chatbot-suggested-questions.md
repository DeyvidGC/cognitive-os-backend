# Preguntas sugeridas del chatbot

Actualizado: 2026-09-20.

`GET /api/v1/chatbot/suggested-questions?limit=1..20 (defecto 5)`

Devuelve una lista de strings: las preguntas mas frecuentes que el chatbot pudo responder (`cognitive.chat_queries` con `answered=true`), agrupadas por texto exacto y ordenadas por frecuencia. Lista vacia si la organizacion aun no tiene historial; el frontend debe caer a sus chips fijos en ese caso (no es un error).

## Acceso y errores

Cualquier miembro de la organizacion (incluye reader). HTTP requiere Bearer y X-Organization-ID.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/chatbot.py), [aplicacion](../../../src/cognitive_os/application/chatbot.py) (`suggested_questions`).
