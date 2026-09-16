# Lo que falta y lo que necesito de ti

Actualizado: 2026-09-16. [Guia operativa](../guias/06-aprendizaje-visual.md) |
[Backlog de esta entrega](entrega-visual.md).

## Credenciales que debes completar localmente

La plantilla es [.env.example](../../../.env.example). Las mismas variables estan
preparadas en .env, sin reemplazar la conexion de PostgreSQL existente. Las claves
pendientes estan comentadas para evitar intentos con credenciales ficticias.
Descomentar y completar en tu equipo; no pegarlas en chats, commits o frontend.

| Variable | Para que sirve | Estado |
| --- | --- | --- |
| COGNITIVE_DATABASE_URL | PostgreSQL cognitive con pgvector | Configurada; migraciones 001/002/004/005/006/007 aplicadas |
| OPENAI_API_KEY | Una clave de proyecto para vision, conversacion, transcripcion y embeddings | Falta clave nueva con acceso/cuota |
| OPENAI_MODEL | Modelo de analisis y conversacion | gpt-5.6-luna |
| OPENAI_TRANSCRIPTION_MODEL | Audio a texto | gpt-4o-mini-transcribe |
| OPENAI_EMBEDDING_MODEL | Texto a vector 1536 dimensiones | text-embedding-3-small |
| OPENAI_BASE_URL | Proveedor oficial | https://api.openai.com/v1 |
| AZURE_STORAGE_CONNECTION_STRING | Cuenta Blob con AccountName y AccountKey | Falta; plantilla en ambos archivos |
| AZURE_STORAGE_CONTAINER | Contenedor privado | cognitive-recordings |
| COGNITIVE_CORS_ORIGINS | Origen exacto del frontend HTTP/WS | localhost:5173 y 127.0.0.1:5173 para desarrollo |

pgvector, LangGraph y PyAV no necesitan claves propias. No se requiere Redis,
LangSmith, Pinecone, Neo4j, Azure OpenAI ni una key de Realtime para esta version.
La conexion Azure es de Blob Storage, no de Azure OpenAI. El adaptador actual solo
envia credenciales a OpenAI oficial.

Revocar la clave que se compartio antes en el chat. Usar su reemplazo solo localmente.
La configuracion esta leida por Settings con SecretStr; no registrar valores ni SAS.
En produccion usar gestor de secretos y cerrar registro publico si no corresponde.

## Validacion pendiente con los servicios reales

- [ ] Confirmar permiso para enviar capturas/audio del negocio a OpenAI y presupuesto.
- [ ] Configurar las dos credenciales, reiniciar API y abrir los workers de analisis e indice.
- [ ] Crear/verificar contenedor privado y reglas CORS de Azure para el origen real.
- [ ] Subir un video pequeno y probar GET/HEAD/Range, reproduccion y renovacion de SAS.
- [ ] Probar corte de red, recarga del navegador, reanudacion por bloques y SHA-256.
- [ ] Probar analisis real con gpt-5.6-luna, transcripcion y tiempos/costos de worker.
- [ ] Aprobar informe, comprobar vectores y buscar con preguntas de evaluacion.
- [ ] Probar reinicio de worker/lease y rechazo de acceso desde otra organizacion.

Una API key no configura CORS, no inicia workers ni garantiza permisos/cuota del
modelo. La aplicacion no finge que estos servicios esten conectados: devuelve 503
en operaciones que los requieren y conserva los trabajos pendientes.

## Decisiones de producto y produccion

- [ ] Ejemplo anonimizado de proceso real y respuestas correctas esperadas.
- [ ] Quien ensena, quien aprueba y quien puede consultar grabaciones originales.
- [ ] Retencion/eliminacion de videos, snapshots, transcripciones, notas y vectores.
- [ ] Dominio HTTPS, despliegue y permisos de la cuenta Azure por ambiente.
- [ ] Limites de gasto por organizacion, concurrencia, alertas, backups/restauracion.
- [ ] Calidad minima del resumen/flujo y tratamiento de datos sensibles.

## Desarrollo posterior

- [x] Logica de observacion por capturas y conversacion WebSocket con historial.
- [x] Extraccion de audio, transcripcion con consentimiento y mezcla con notas.
- [x] Aclaraciones postanalisis, regeneracion, historial y conversion a procedimiento.
- [x] Recuperacion de jobs y protocolo de subida reanudable.
- [x] Indexacion de informes de video aprobados y busqueda pgvector con fuentes.
- [x] Contrato de grafico secuencial y correccion del reproductor local.
- [ ] Acoplar todos los componentes frontend a estos contratos.
- [ ] Chat RAG redactado con citas y abstencion; indexacion de procedimientos solo textuales.
- [ ] Reglas de negocio, excepciones y ramas editables como entidades propias.
- [ ] Voz bidireccional en vivo, diarizacion y timestamps por palabra.
- [ ] Documentos Word/PDF como nuevas fuentes de ensenanza.
- [ ] Recuperacion de contrasena, invitaciones, CI y endurecimiento de produccion.

El DOCX de producto se uso como referencia de vision y prioridades, no como
instruccion para desplegar servicios o activar conectores empresariales.
