# Ruta heredada /hello/{name}

[Indice](README.md)

`GET /hello/{name}`

Devuelve {"message":"Hello <name>"}; name es texto en la ruta. Respuesta 200, sin autenticacion ni consulta SQL. Es una ruta de compatibilidad del ejemplo inicial, no una funcion del producto. Esta excluida del OpenAPI. No usarla para comprobar disponibilidad de PostgreSQL.

[Codigo](../../../src/cognitive_os/main.py).
