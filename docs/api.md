# API implementada

Prefijo `/api/v1`. Contratos completos y pruebas interactivas en `/docs`.

## Autenticacion

1. `POST /auth/register`: JSON con email, password, display_name y organization_name.
   Devuelve perfil y membresia owner. Requiere COGNITIVE_REGISTRATION_ENABLED=true.
2. `POST /auth/login`: JSON con email y password. Devuelve access_token y expires_at.
3. Usar `Authorization: Bearer <access_token>` en cada llamada protegida.
   En Swagger pegar solo el token en Authorize.
4. `GET /auth/me`: perfil y organizaciones accesibles.
5. `POST /auth/logout`: revoca el token actual; devuelve 204.

Los recursos de negocio tambien requieren `X-Organization-ID` de una membresia
del usuario. El encabezado selecciona organizacion, nunca concede acceso.
Cada registro crea una organizacion nueva, no permite ingresar a una existente.

Contrasenas de 12 a 128 caracteres, hashes Argon2id. Tokens aleatorios opacos
(no JWT), almacenados como hashes SHA-256, con caducidad de una hora configurable.
Cinco errores de login bloquean la cuenta durante 15 minutos. Limite adicional
de 20 llamadas de autenticacion por IP y minuto, por proceso. Varios workers
requieren un limitador compartido en el gateway. Desplegar con HTTPS.
El correo es un identificador normalizado; su propiedad aun no se verifica.

## Sesiones

| Metodo | Ruta | Funcion |
| --- | --- | --- |
| POST / GET | `/learning-sessions` | Crear con objective, application_name y consent=true; listar con limit/offset |
| GET | `/learning-sessions/{id}` | Consultar sesion |
| POST / GET | `/learning-sessions/{id}/events` | Registrar o listar mensajes/transcripciones |
| POST / GET | `/learning-sessions/{id}/evidence` | Subir o listar capturas |
| GET | `/evidence/{id}/file` | Descargar imagen con autorizacion |
| POST / GET | `/learning-sessions/{id}/clarifications` | Crear o listar preguntas |
| PUT | `/learning-sessions/{id}/clarifications/{question_id}/answer` | Registrar respuesta |
| POST | `/learning-sessions/{id}/finish` | Cerrar captura y reservar trabajo; 202 |
| GET | `/jobs/{id}` | Consultar trabajo |

Ejemplo de evento:

```json
{"idempotency_key":"evento-001","sequence_number":0,"offset_ms":0,"event_type":"message","text":"Abro la pantalla de cotizaciones."}
```

Reintentar la misma clave y contenido devuelve el evento existente; reutilizarla
con otro contenido responde 409. La secuencia es unica por sesion. Los tipos
permitidos desde el cliente son message y transcript.

Capturas: multipart con campo file, PNG/JPEG/WebP validado y limite de 10 MiB.
Los archivos quedan en `.data/evidence` (fuera de Git), con nombres generados.
captured_at registra la recepcion del archivo en el servidor. No hay analisis de IA.
El proxy de despliegue tambien debe limitar el cuerpo antes del parser multipart.

Owner/author crean sesiones; solo su autor o un owner las modifica. Reviewer
consulta y plantea dudas. Reader no accede a capturas crudas. Para cerrar debe
existir un evento o evidencia y todas las dudas deben estar resueltas. El cierre
es atomico e idempotente. Sin worker, job sigue pending y sesion processing.

## Procedimientos

| Metodo | Ruta | Funcion |
| --- | --- | --- |
| POST / GET | `/procedures` | Crear o listar |
| POST / GET | `/procedures/{id}/versions` | Crear borrador vacio o listar versiones |
| GET | `/procedure-versions/{id}` | Consultar version |
| POST / GET | `/procedure-versions/{id}/steps` | Crear o listar pasos |
| PUT | `/procedure-versions/{id}/steps/{step_id}` | Reemplazar datos de paso |
| PUT | `/procedure-versions/{id}/steps/{step_id}/evidence` | Vincular evidence_id con explanation |
| PUT / GET | `/procedure-versions/{id}/tutorial` | Guardar content Markdown o consultar |
| POST | `/procedure-versions/{id}/submit` | Enviar a revision |
| POST | `/procedure-versions/{id}/return` | Devolver a borrador |
| POST | `/procedure-versions/{id}/approve` | Aprobar |
| POST | `/procedure-versions/{id}/publish` | Publicar y preparar busqueda textual |
| POST | `/procedure-versions/{id}/retire` | Retirar publicacion |
| GET | `/knowledge/search?q=cotizacion` | Buscar texto publicado con referencias |

Paso: position, instruction, expected_result, origin y validation_status.
Origenes: observed, user_explained, inferred. Validacion: pending, confirmed, rejected.
El autor declara estos datos y el reviewer los comprueba. Pasos observed/inferred
requieren evidencia; posiciones consecutivas desde 1 y todos confirmed para revision.
El tutorial debe existir antes de enviar la version a revision.

Owner/author editan borradores; owner/reviewer aprueban, publican o retiran.
Owner puede aprobar contenido propio en esta primera version. El contenido aprobado
no se edita mediante la API; las correcciones requieren otra version.
Publicar retira la version anterior, crea fragmentos textuales desde los pasos y
activa la nueva version en una transaccion. Se auditan las operaciones editoriales.
Reader solo consulta versiones publicadas y tutoriales; retirar oculta el contenido
de sus consultas. La busqueda filtra organizacion y published, y devuelve
version_id, version_number y step_id. Es textual, no semantica ni generada por IA.
Los clientes deben renderizar Markdown sin ejecutar HTML embebido.

## Pendientes

No hay recuperacion de contrasenas, MFA, invitaciones, administracion de miembros,
retencion/eliminacion de archivos ni edicion de decisiones ramificadas.
No hay RLS: el aislamiento lo aplican endpoints y claves compuestas. Usar una cuenta
SQL de la API con permisos limitados, distinta de postgres. Una caida abrupta entre
guardar un archivo y su registro SQL puede dejar un archivo huerfano; se necesitara
una tarea de limpieza. Ante errores SQL normales se compensa borrando el nuevo archivo.
