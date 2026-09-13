# Guia y seguimiento de Cognitive OS

Actualizado: 13 de septiembre de 2026, zona America/Bogota.

Esta carpeta explica el trabajo realizado, su motivo y como probarlo. El estado
del codigo se verifico al escribirla. Los resultados de pruebas y cambios en la
base real que se citan pertenecen a las verificaciones registradas en la conversacion;
esta entrega de documentacion no vuelve a ejecutar migraciones ni modifica datos.

## Por donde empezar

1. [Resumen y estructura de la API](guias/01-arquitectura.md).
2. [Como probar los endpoints y sus permisos](guias/02-probar-api.md).
3. [Ejemplo completo: desde registro hasta busqueda](guias/03-recorrido.md).
4. [Estructura y relaciones de la base de datos](base-de-datos/01-estructura.md).
5. [Diccionario de las tablas](base-de-datos/02-tablas.md).
6. [Base vectorial: concepto, estado y uso](base-de-datos/03-vectorial.md).
7. [Ficha individual de cada endpoint](endpoints/README.md).
8. [Trabajo del 12 de septiembre](bitacora/2026-09-12.md) y [del 13 de septiembre](bitacora/2026-09-13.md).

## Estado del producto

| Parte | Estado al corte documental |
| --- | --- |
| Ramas main/develop y estructura FastAPI | Creadas; develop usada para desarrollo |
| PostgreSQL cognitive | Migraciones 001 y 004 aplicadas segun la verificacion anterior |
| Autenticacion local y recursos de negocio | Implementados; 35 operaciones versionadas |
| Rutas heredadas del ejemplo | 2, fuera del OpenAPI |
| Conexion directa de la API a PostgreSQL real | Pendiente de configurar la credencial en .env segun el ultimo estado registrado |
| Pruebas | Ultima ejecucion registrada: 17 correctas contra PostgreSQL temporal |
| Publicacion y busqueda textual | Implementadas mediante el flujo editorial manual |
| pgvector y chunk_embeddings | Migracion preparada, no aplicada segun la ultima comprobacion |
| Worker, LangGraph y respuestas generadas por IA | Pendientes |

Los diagramas usan Mermaid. Un visor compatible los renderiza; en un editor de
texto se ve su codigo. Cada diagrama tiene tambien una explicacion escrita.

## Mantener la documentacion

[Plantilla diaria](bitacora/PLANTILLA.md) y [reglas de actualizacion](COMO_ACTUALIZAR.md).
Las bitacoras son un registro manual: no hay una tarea automatica programada.
La ficha del endpoint describe su comportamiento actual; la bitacora conserva
la historia y no debe reescribirse para aparentar que algo ya estaba implementado.

La [arquitectura inicial](../arquitectura-inicial.md) es una propuesta historica
y contiene referencias a otra base de trabajo; para saber que existe ahora usar
esta guia, las migraciones y el codigo.
