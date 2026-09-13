# Como probar la API

[Indice](../README.md) | [Endpoints](../endpoints/README.md)

## Preparacion

Desde la raiz del proyecto, instalar las dependencias con
`.venv/Scripts/python.exe -m pip install -e '.[dev]'`.
La configuracion se describe en [.env.example](../../../.env.example). Crear o
completar `.env` localmente, sin publicar contrasenas en Git ni en estas guias.

```dotenv
COGNITIVE_DATABASE_URL="postgresql+psycopg://USUARIO:CLAVE_CODIFICADA@localhost:5432/cognitive"
COGNITIVE_REGISTRATION_ENABLED=true
COGNITIVE_TOKEN_TTL_SECONDS=3600
COGNITIVE_EVIDENCE_DIRECTORY=.data/evidence
```

La clave de la URL debe codificar caracteres especiales como @, : y /. Usar una
cuenta PostgreSQL de la API con permisos sobre cognitive, distinta del superusuario.
La cuenta de PostgreSQL conecta el servidor; email/password de /auth/login son
cuentas del producto. No son las mismas credenciales.

Antes de utilizar una base nueva ejecutar 001_initial.sql y 004_local_auth.sql
en Query Tool. Sobre la base ya preparada no repetirlas. Consultar
`SELECT * FROM cognitive.schema_migrations ORDER BY version;`.
002_pgvector es opcional e independiente; 003_Query no es una migracion.

Iniciar con `.venv/Scripts/python.exe -m uvicorn cognitive_os.main:app --reload`.
Abrir [Swagger](http://127.0.0.1:8000/docs). Que /health responda ok no demuestra
que SQL este configurado: los recursos de datos pueden responder 503.

## Autenticacion y seleccion de organizacion

```mermaid
sequenceDiagram
    participant C as Cliente
    participant A as API
    participant D as PostgreSQL
    C->>A: register con correo y contrasena
    A->>D: Hash Argon2, usuario y organizacion owner
    A-->>C: Perfil y organization_id
    C->>A: login
    A->>D: Verificar hash y guardar hash del token
    A-->>C: access_token y caducidad
    C->>A: Bearer token y X-Organization-ID
    A->>D: Comprobar token y membresia
    A-->>C: Recurso autorizado
```

En Swagger, usar Authorize y pegar solo access_token. En recursos de negocio,
rellenar x-organization-id con el UUID devuelto por registro o /auth/me. Copiar
UUID de respuestas reales; los nombres como SESSION_ID de las guias son marcadores.

El token es opaco, no JWT. Logout revoca solo el token actual. Expira por defecto
en una hora. Cinco contrasenas incorrectas bloquean 15 minutos la cuenta; existe
ademas un limite por proceso de 20 llamadas de autenticacion por IP/minuto.

## Permisos

| Operacion | owner | author | reviewer | reader |
| --- | --- | --- | --- | --- |
| Crear sesiones y procedimientos | Si | Si | No | No |
| Consultar capturas de la organizacion | Si | Si | Si | No |
| Editar captura y responder dudas | Cualquiera propia de la organizacion | Solo si es autor de la sesion | No | No |
| Plantear dudas durante captura | Si | Si | Si | No |
| Editar borradores y tutoriales | Si | Si | No | No |
| Aprobar, publicar y retirar | Si | No | Si | No |
| Consultar versiones no publicadas | Si | Si | Si | No |
| Buscar conocimiento publicado | Si | Si | Si | Si |

Todos los permisos se restringen a membresias existentes. El encabezado no crea
acceso. No hay endpoints de invitaciones o gestion de roles todavia. Owner puede
aprobar su propio trabajo; aun no hay separacion obligatoria de funciones.

## Errores y respuestas

| Codigo | Significado |
| --- | --- |
| 200 | Consulta o cambio completado; eventos reintentados tambien usan 200 |
| 201 | Recurso creado |
| 202 | Job guardado; no significa procesamiento terminado |
| 204 | Logout sin cuerpo |
| 401 | Token ausente/invalido/expirado, o credenciales incorrectas |
| 403 | Sin membresia, rol insuficiente o registro deshabilitado |
| 404 | Recurso ausente o no visible para el usuario |
| 409 | Estado incompatible, unicidad o clave idempotente con otro contenido |
| 413 / 415 | Captura demasiado grande / imagen no admitida o invalida |
| 422 | Entrada no cumple el contrato |
| 429 | Limite de autenticacion |
| 503 | Conexion ausente, SQL inaccesible o migraciones faltantes |

Las listas paginadas devuelven arrays, no un objeto con total. Solo las fichas
que muestran limit/offset admiten paginacion. PUT de un paso recibe sus campos
completos; no hay PATCH para modificar un unico atributo.
