# Requisitos y checklist

[Plan](README.md) | [Backlog](product-backlog.md)

Estos requisitos consolidan lo construido y el alcance propuesto. Los elementos
de produccion son propuestas tecnicas, pendientes de priorizacion contigo.

## Plataforma y acceso

- [x] RF-01: API FastAPI modular con rutas /api/v1 y OpenAPI.
- [x] RF-02: Registro local con correo y contrasena, organizacion y propietario.
- [x] RF-03: Login, perfil y logout con token opaco revocable y expiracion.
- [x] RF-04: Comprobar membresia y roles owner/author/reviewer/reader.
- [ ] RF-05: Invitaciones y administracion de miembros (propuesto).
- [ ] RF-06: Recuperacion de contrasena y verificacion de correo (propuesto).

## Captura de conocimiento

- [x] RF-07: Crear, listar y consultar sesiones de aprendizaje.
- [x] RF-08: Registrar mensajes/transcripciones como texto e idempotencia de eventos.
- [x] RF-09: Subir y descargar imagenes PNG/JPEG/WebP con validacion y permisos.
- [x] RF-10: Crear, consultar y responder aclaraciones manualmente.
- [x] RF-11: Cerrar captura y guardar un trabajo durable pending atomicamente.
- [ ] RF-12: Procesar el trabajo con un worker, reintentos y recuperacion de fallos.
- [ ] RF-13: Orquestar extraccion/validacion con LangGraph y modelos de IA.
- [ ] RF-14: Recibir audio y transcribirlo; hoy solo se acepta texto de transcripcion.

## Edicion y publicacion

- [x] RF-15: Crear y consultar procedimientos y versiones.
- [x] RF-16: Editar pasos y vincular evidencia en borrador.
- [x] RF-17: Guardar tutorial Markdown.
- [x] RF-18: Enviar a revision, devolver, aprobar, publicar y retirar versiones.
- [x] RF-19: Proteger contenido aprobado/publicado contra edicion por la API.
- [x] RF-20: Generar fragmentos textuales al publicar y retirar la publicacion anterior.
- [ ] RF-21: Editar decisiones y ramificaciones (tabla decisions preparada, API pendiente).

## Consulta y vectores

- [x] RF-22: Buscar texto en versiones publicadas de la organizacion con referencias.
- [ ] RF-23: Instalar pgvector y aplicar 002 en la base real; SQL preparado.
- [ ] RF-24: Generar embeddings versionados por modelo y persistirlos por fragmento.
- [ ] RF-25: Busqueda semantica con filtros de organizacion y estado publicado.
- [ ] RF-26: Chat RAG con referencias verificables y respuesta sin evidencia suficiente.

## Requisitos tecnicos

- [x] RNF-01: PostgreSQL y SQLAlchemy con relaciones y restricciones multi-organizacion.
- [ ] RNF-02: Verificar el flujo HTTP con la conexion real configurada; pruebas aisladas no la sustituyen.
- [x] RNF-03: Hash Argon2id, hash de tokens y errores de validacion sin eco de contrasenas.
- [x] RNF-04: Limites locales de autenticacion y bloqueo temporal por fallos.
- [ ] RNF-05: Limites distribuidos para multiples procesos/replicas (propuesto).
- [x] RNF-06: Arranque explicito mediante Uvicorn y entrada Python.
- [ ] RNF-07: Validar manualmente el boton Run de PyCharm en el equipo del usuario.
- [x] RNF-08: Suite automatizada con PostgreSQL temporal y pruebas de aislamiento/concurrencia.
- [ ] RNF-09: CI que ejecute la suite y controles antes de integrar cambios (propuesto).
- [x] RNF-10: Documentacion por endpoint, DB, vectores y bitacora en Markdown.
- [ ] RNF-11: Despliegue con TLS, gestion de secretos y almacenamiento durable (propuesto).
- [ ] RNF-12: Copias de seguridad y prueba de restauracion (propuesto).
- [ ] RNF-13: Metricas, trazas, alertas y diagnostico de dependencias (propuesto).
- [ ] RNF-14: Evaluacion de calidad RAG, privacidad, retencion y pruebas de carga (propuesto).

## Fuera del alcance implementado

No hay frontend de producto, SSO, MFA, respuestas generadas por IA ni procesamiento
de voz. Swagger es una herramienta de prueba, no el producto final. El aislamiento
actual depende de la API y de restricciones SQL; no se afirma que exista RLS.
