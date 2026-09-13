# Registrar cuenta

[Indice](README.md) | [Contratos de datos](contratos.md)

`POST /api/v1/auth/register`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Normaliza el correo, calcula Argon2id y crea usuario, organizacion nueva y membresia owner en una transaccion. No inicia sesion ni permite unirse a una organizacion existente.

## Acceso

Registro publico solo si COGNITIVE_REGISTRATION_ENABLED=true.

No necesita token. 

## Entrada

Cuerpo: `application/json`.

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `email` | string (email) | Si | - |
| `password` | string (password) | Si | min. caracteres: 12; max. caracteres: 128 |
| `display_name` | string | Si | min. caracteres: 1; max. caracteres: 200 |
| `organization_name` | string | Si | min. caracteres: 1; max. caracteres: 200 |

Ejemplo orientativo; sustituir IDs simbolicos y no usar esta clave en cuentas reales:

```json
{
  "email": "ana@example.com",
  "password": "UnaClaveLarga-De-Ejemplo",
  "display_name": "Ana",
  "organization_name": "Equipo de prueba"
}
```

## Respuesta

Exito: **201**. `UserResponse`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

users, organizations, memberships, local_credentials.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/auth.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
