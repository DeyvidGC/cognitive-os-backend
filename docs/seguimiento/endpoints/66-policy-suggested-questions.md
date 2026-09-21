# Preguntas sugeridas de una poliza

Actualizado: 2026-09-20.

`GET /api/v1/policies/{policy_id}/suggested-questions`

Igual que [65-chatbot-suggested-questions.md](65-chatbot-suggested-questions.md) pero filtrado a un solo `policy_id` (`cognitive.chat_queries.policy_id`), para el panel IA del visor de politicas. Lista vacia si la poliza aun no tiene preguntas respondidas; el frontend cae a sus chips fijos.

## Acceso y errores

Cualquier miembro de la organizacion (incluye reader). 404 si la poliza no existe en la organizacion del token.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/policies.py), [aplicacion](../../../src/cognitive_os/application/chatbot.py) (`suggested_questions`, reutilizada desde `policies.py`).
