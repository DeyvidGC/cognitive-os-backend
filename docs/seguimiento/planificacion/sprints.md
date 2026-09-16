# Sprints, tablero y criterios de cierre

Incremento 2026-09-16: [sprints visuales y validacion real pendiente](entrega-visual.md).

[Plan](README.md) | [Backlog](product-backlog.md)

Propuesta: iteraciones de una semana una vez acordados disponibilidad y alcance.
No se asignan fechas futuras sin ese acuerdo. El trabajo previo se agrupa como
baseline retrospectivo: no se afirma que se haya ejecutado con Scrum formal.

## Baseline: trabajo existente

- [x] Estructura, autenticacion, aislamiento, captura y flujo editorial manual.
- [x] Busqueda textual, contratos OpenAPI y pruebas con PostgreSQL aislado.
- [x] Documentacion explicada de arquitectura, endpoints y base de datos.

Historias: PB-03/04/05/06/07/21. Evidencia: codigo, tests y bitacoras del 12/13.

## Sprint 1: arranque confiable y procesamiento durable

Objetivo: que se pueda arrancar sin ambiguedad y que cerrar una captura no deje
un trabajo permanentemente pending. Historias propuestas: PB-01/02/08/18.

- [x] Arranque explicito, configuracion compartida para PyCharm y regresiones.
- [ ] Confirmar ejecucion desde el IDE y conexion HTTP a PostgreSQL real.
- [x] Implementar worker textual con reclamo atomico, leases, limite de reintentos y errores.
- [x] Probar concurrencia, rechazo de worker vencido y reintentos del worker.
- [ ] Preparar CI para API y worker.

Demo de cierre: iniciar API/worker, cerrar una captura y observar una transicion
de job real con resultado o fallo controlado. No fingir consolidacion con IA.
El sprint no esta terminado por tener resuelto el arranque.

## Sprint 2: borradores con IA supervisada

Historias: PB-09. Requiere worker estable y decision de proveedor/presupuesto.

- [ ] Definir contratos de entrada/salida, limites y politicas de datos.
- [ ] Integrar LangGraph para extraccion, validacion y aclaraciones.
- [ ] Conservar evidencias y persistir borradores sin publicacion automatica.
- [ ] Probar fallos de proveedor, salidas invalidas y reanudacion.

Demo: una captura produce un borrador revisable con evidencia; un humano publica.

## Sprint 3: recuperacion semantica

Historias: PB-10/11/12. Bloqueo actual: extension pgvector no instalada.

- [x] Verificar pgvector 0.8.6 y tabla chunk_embeddings en PostgreSQL real.
- [ ] Elegir modelo de embeddings compatible con la dimension del esquema.
- [ ] Indexar fragmentos publicados con reintentos e idempotencia.
- [ ] Implementar busqueda semantica y pruebas de filtros/retirada de versiones.

Demo: una parafrasis encuentra un procedimiento publicado de la organizacion
correcta, sin recuperar borradores ni informacion de otra organizacion.

## Sprint 4: respuestas RAG y evaluacion

Historias: PB-13 y parte de PB-20; dividir PB-20 antes de comprometer capacidad.

- [ ] Construir respuestas con referencias comprobables.
- [ ] Manejar ausencia de evidencia y documentos con instrucciones maliciosas.
- [ ] Medir calidad, latencia y coste sobre un conjunto de preguntas acordado.

Demo: preguntas respondidas con fuentes accesibles y abstencion cuando no hay base.

## Siguientes iteraciones por priorizar

Miembros, recuperacion, decisiones, voz y operacion: PB-14/15/16/17/19 y resto PB-20.
No se consideran comprometidos ni caben automaticamente en un mismo sprint.

## Tablero al corte

| Columna | Elementos |
| --- | --- |
| Implementado en codigo | PB-03/04/05/06/07/21 |
| Por validar en entorno usuario | PB-01 (IDE), PB-02 (conexion real) |
| Siguiente trabajo propuesto | PB-08 y PB-18 |
| Preparado parcialmente | PB-10 (solo migracion) |
| Pendiente dependencias | PB-09/11/12/13 |
| Sin compromiso de sprint | PB-14/15/16/17/19/20 |

## Definition of Ready

Una historia entra a un sprint cuando tiene alcance, aceptacion, dependencias,
riesgos y configuracion de prueba definidos. Historias L deben descomponerse si
superan la capacidad acordada. No comenzar integraciones pagadas sin configuracion
y limites de gasto acordados.

## Definition of Done

- [ ] Criterios de aceptacion de la historia cumplidos.
- [ ] Permisos, aislamiento y validacion de entrada comprobados.
- [ ] Pruebas apropiadas pasan; se documenta cualquier omision.
- [ ] Migraciones necesarias revisadas y probadas en entorno aislado.
- [ ] Contratos, ficha del endpoint, checklist y bitacora actualizados.
- [ ] Sin secretos/versionados ni cambios destructivos no solicitados.
- [ ] Demo reproducible y limitaciones explicitas.

Esta lista es una plantilla por historia, no una declaracion de que todo el
producto ya esta terminado. Al cerrar una iteracion registrar demo, resultado,
pendientes trasladados y una mejora concreta del proceso.
