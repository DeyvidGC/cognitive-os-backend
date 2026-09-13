# Recorrido completo de ejemplo

[Indice](../README.md)

Ejemplo manual en Swagger, con una cuenta owner de prueba. Supone conexion y
migraciones listas. Todos los valores son ficticios y las claves solo ilustrativas.

## 1. Registrarse e ingresar

POST /api/v1/auth/register:

```json
{"email":"ana@example.com","password":"UnaClaveLarga-De-Ejemplo","display_name":"Ana","organization_name":"Equipo de prueba"}
```

Conservar memberships[0].organization_id. Hacer POST /api/v1/auth/login con
email/password y usar access_token en Authorize. Indicar X-Organization-ID en
todos los pasos siguientes.

## 2. Explicar el proceso

POST /api/v1/learning-sessions:

```json
{"objective":"Explicar como registrar una cotizacion","application_name":"CRM","consent":true}
```

Conservar id como SESSION_ID. POST /api/v1/learning-sessions/SESSION_ID/events:

```json
{"idempotency_key":"explicacion-1","sequence_number":0,"offset_ms":0,"event_type":"message","text":"Registro los datos y verifico que la cotizacion se haya guardado."}
```

Opcionalmente subir una imagen en /learning-sessions/SESSION_ID/evidence, mediante
file multipart. Crear y responder preguntas en /clarifications si hacen falta.
POST /learning-sessions/SESSION_ID/finish cierra la captura y devuelve un job.
Consultar /jobs/JOB_ID muestra pending: el procesamiento de IA aun no existe.

## 3. Crear el procedimiento manual

POST /api/v1/procedures:

```json
{"title":"Registrar cotizacion","scope":"Registro inicial de cotizaciones del equipo comercial"}
```

Conservar id como PROCEDURE_ID. POST /procedures/PROCEDURE_ID/versions con
`{"summary":"Flujo explicado por Ana"}` crea un borrador vacio. Opcionalmente
incluir source_session_id con el UUID de la captura para vincularla.
Conservar id como VERSION_ID y crear el paso:

POST /api/v1/procedure-versions/VERSION_ID/steps:

```json
{"position":1,"instruction":"Registrar los datos de la cotizacion.","expected_result":"La cotizacion aparece guardada.","origin":"user_explained","validation_status":"confirmed"}
```

Este origen corresponde a la explicacion manual del experto. No marcar observed
sin una observacion respaldada. Si se usa observed/inferred, vincular una captura
con PUT /procedure-versions/VERSION_ID/steps/STEP_ID/evidence y un body con
evidence_id y explanation. Si hay source_session_id, la imagen debe ser de esa sesion.

## 4. Revisar y publicar

PUT /api/v1/procedure-versions/VERSION_ID/tutorial:

```json
{"content":"# Registrar cotizacion\n1. Registrar los datos.\n2. Comprobar que la cotizacion se guardo."}
```

Sin cuerpo, ejecutar en orden:

1. POST /procedure-versions/VERSION_ID/submit: draft pasa a in_review.
2. POST /procedure-versions/VERSION_ID/approve: in_review pasa a approved.
3. POST /procedure-versions/VERSION_ID/publish: approved pasa a published.

Los dos ultimos pasos necesitan owner/reviewer. Todos los pasos deben estar
confirmed, con posiciones consecutivas y respaldo cuando corresponda. Una revision
puede devolverse a draft con /return. Tras aprobar se requiere otra version para
corregir; no hay reapertura de approved.

## 5. Consultar lo publicado

GET /api/v1/knowledge/search?q=cotizacion devuelve fragmentos con version_id y
step_id. GET /procedure-versions/VERSION_ID/tutorial devuelve el Markdown.
No hay respuesta conversacional de IA: esta consulta usa busqueda textual.
Retirar con POST /procedure-versions/VERSION_ID/retire oculta esa version de reader
y de la busqueda, sin borrar el historial.

## Lo que este recorrido no hace

No completa el job de captura, genera un tutorial con IA ni crea embeddings.
El contenido y la aprobacion son manuales. La consulta vectorial futura se explica
en la [guia de pgvector](../base-de-datos/03-vectorial.md).
