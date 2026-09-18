# Guia y seguimiento de Cognitive OS

## Actualizacion 2026-09-17

[Word/PDF con capturas y diagramas BPMN](guias/10-documentos-y-bpmn.md):
contratos, pantallas, verificacion y limites de exportacion.

[Procesamiento automatico, pruebas reales y grafo v2](guias/09-procesamiento-y-grafo-v2.md)
| [Bitacora](bitacora/2026-09-17.md). Credenciales verificadas, workers integrados
en desarrollo y flujo real de analisis/indexacion comprobado.

## Entrega vigente: 2026-09-16

- [Flujo visual, configuracion y contratos frontend](guias/06-aprendizaje-visual.md).
- [Mejoras del frontend por prioridad](guias/07-mejoras-frontend.md).
- [Conectar Vercel con el backend local](guias/08-vercel-localhost.md).
- [Video, tablas y uso de pgvector](base-de-datos/04-video-y-vectores.md).
- [Checklist, backlog y sprints](planificacion/entrega-visual.md).
- [Bitacora y pruebas](bitacora/2026-09-16.md).
- [Fichas de endpoints nuevos](endpoints/visual-catalogo.md).

El contenido inferior conserva el corte anterior. Esta entrega aplica migraciones
aditivas 005/006/007 a la base local, sin borrar datos existentes. Las pruebas con
inserciones usan PostgreSQL aislado.

Actualizado: 13 de septiembre de 2026, zona America/Bogota.

Esta carpeta explica el trabajo realizado, su motivo y como probarlo. El estado
del codigo se verifico al escribirla. Los resultados de pruebas y cambios en la
base real que se citan pertenecen a las verificaciones registradas en la conversacion.
La entrega de arranque vuelve a ejecutar pruebas y migraciones solamente contra
PostgreSQL temporal aislado; no modifica datos de la base real.

## Por donde empezar

- [Orquestacion implementada: captura de texto a borrador](guias/05-orquestacion.md).

- [Solucion de arranque en PyCharm y consola](guias/04-arranque.md).
- [Requisitos con checklist, product backlog y sprints](planificacion/README.md).
- [Pendientes y lo que necesito de ti para avanzar](planificacion/lo-que-necesito.md).

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
| Pruebas | 29 correctas contra PostgreSQL temporal, con orquestacion simulada |
| Publicacion y busqueda textual | Implementadas mediante el flujo editorial manual |
| pgvector y chunk_embeddings | Verificados: extension 0.8.6 y tabla presentes en la base real |
| Worker y LangGraph | Implementados para borradores desde texto; prueba con proveedor real pendiente |

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
