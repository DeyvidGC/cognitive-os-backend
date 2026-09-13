# Product backlog

[Plan](README.md) | [Requisitos](requisitos.md) | [Sprints](sprints.md)

P0 = bloquea el uso/desarrollo inmediato; P1 = siguiente valor principal;
P2 = mejora posterior. Estimaciones relativas: S pequeno, M medio, L grande.
Son orientativas, no duraciones ni compromisos. Terminado significa implementado,
no certificado para produccion. Cada fila expresa una historia y su aceptacion.

| ID | Historia / valor | Requisitos | Prioridad | Tamano | Estado | Criterio de aceptacion |
| --- | --- | --- | --- | --- | --- | --- |
| PB-01 | Como desarrollador, arrancar sin autodeteccion del IDE | RNF-06/07 | P0 | S | Implementado; Run visual pendiente | Entrada Python y Uvicorn sirven health/docs; configuracion de IDE seleccionada y probada |
| PB-02 | Como usuario, operar con mi PostgreSQL real | RNF-02 | P0 | S | Pendiente | Configuracion privada valida; registro/login y recurso persistido por HTTP sin exponer credenciales |
| PB-03 | Como usuario, entrar con correo/contrasena | RF-02/03, RNF-03/04 | P0 | M | Implementado | Registro/login/me/logout, expiracion, revocacion y errores seguros cubiertos |
| PB-04 | Como organizacion, aislar mis recursos | RF-04, RNF-01 | P0 | M | Implementado | Acceso cruzado rechazado y roles comprobados en recursos |
| PB-05 | Como autor, capturar un proceso con evidencia | RF-07/11 | P1 | L | Implementado | Eventos idempotentes, imagenes validas, aclaraciones y cierre atomico |
| PB-06 | Como revisor, publicar conocimiento validado | RF-15/20 | P1 | L | Implementado | Borrador/revision/aprobacion/publicacion y concurrencia verificadas |
| PB-07 | Como lector, encontrar procedimientos publicados | RF-22 | P1 | M | Implementado | Busqueda textual restringida por organizacion y publicacion |
| PB-08 | Como autor, ver completarse el procesamiento | RF-12 | P1 | L | Pendiente | Worker reclama un job una sola vez, registra resultado/error, reintenta con limite y recupera leases vencidos; pruebas con dos workers |
| PB-09 | Como autor, obtener un borrador asistido | RF-13 | P1 | L | Pendiente | Grafo LangGraph valida salida estructurada, conserva referencias, pide aclaracion y nunca publica automaticamente; pruebas con proveedor simulado |
| PB-10 | Como administrador, habilitar vectores | RF-23 | P1 | M | Preparado | Extension disponible y migracion 002 aplicada/verificada en cognitive; no altera tablas ajenas |
| PB-11 | Como sistema, indexar fragmentos semanticamente | RF-24 | P1 | L | Pendiente | Modelo/dimension definidos, embeddings reproducibles por contenido, upsert idempotente y reintentos; ningun secreto en logs |
| PB-12 | Como lector, buscar por significado | RF-25 | P1 | M | Pendiente | Query vectorizada con mismo modelo, filtros previos de organizacion/publicacion y pruebas de aislamiento |
| PB-13 | Como lector, preguntar y verificar la respuesta | RF-26 | P1 | L | Pendiente | Respuesta sustentada en fragmentos accesibles, referencias verificadas, rechazo sin evidencia y evaluacion contra inyeccion de instrucciones |
| PB-14 | Como propietario, gestionar miembros | RF-05 | P2 | M | Propuesto | Invitacion expira, solo owner gestiona roles y se protege el ultimo owner |
| PB-15 | Como usuario, recuperar acceso | RF-06 | P2 | M | Propuesto | Token de un uso/expirable, sin enumerar correos y revocacion de sesiones segun politica |
| PB-16 | Como autor, describir ramificaciones | RF-21 | P2 | M | Pendiente | Decisiones validas en borrador con referencias a pasos de la misma version |
| PB-17 | Como autor, capturar voz | RF-14 | P2 | L | Pendiente | Limites de audio, transcripcion trazable, consentimiento/retencion y errores definidos |
| PB-18 | Como equipo, integrar cambios comprobados | RNF-09 | P1 | M | Propuesto | CI levanta PostgreSQL aislado, aplica migraciones y ejecuta pruebas sin secretos reales |
| PB-19 | Como operador, desplegar y recuperar el servicio | RNF-05/11/12/13 | P2 | L | Propuesto | TLS/secretos, backups restaurados, evidencia durable, limites distribuidos y alertas verificadas |
| PB-20 | Como responsable, medir calidad y riesgo | RNF-14 | P2 | L | Propuesto | Dataset de evaluacion, umbrales acordados, pruebas de carga y politica de privacidad |
| PB-21 | Como propietario, entender el avance | RNF-10 | P1 | M | Implementado | Fichas de 35 operaciones y 2 rutas heredadas, contratos, diagramas, requisitos y bitacora |

Dependencias principales: PB-08 precede PB-09; PB-10 precede PB-11; PB-11 precede
PB-12 y PB-12 precede PB-13. PB-02 es necesario para validar el uso con la base real,
pero las pruebas de desarrollo deben seguir usando una base aislada.
