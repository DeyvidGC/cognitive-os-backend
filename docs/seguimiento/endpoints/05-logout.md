# Cerrar sesion

[Indice](README.md) | [Contratos de datos](contratos.md)

`POST /api/v1/auth/logout`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Marca revoked_at en el token actual. Otros tokens del mismo usuario siguen activos. Repetir con el token revocado responde 401.

## Acceso

Token Bearer valido; no requiere X-Organization-ID.

Enviar `Authorization: Bearer <token>`. 

## Entrada

Sin cuerpo de solicitud.

## Respuesta

Exito: **204**. Sin cuerpo.

## Persistencia y limites

auth_tokens.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/auth.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
