# Incremento de aprendizaje visual

## Incremento documental: 2026-09-17

- [x] PDF y Word con capturas del video, pasos, fuentes y aclaraciones resueltas.
- [x] Diferenciar documento aprobado de borrador y bloquear preguntas pendientes.
- [x] BPMN de actividades humanas, decisiones y descarga; visor integrado en front.
- [x] PDF real revisado; pruebas de permisos y exportacion automatizadas.
- [ ] Revisar paginacion DOCX en Word y probar importacion en Bizagi.
- [ ] Sprint siguiente: exportaciones en cola y documentos persistidos en Blob.
- [ ] Backlog: anonimizar capturas y editar BPMN con multiples responsables.

[Contratos y limites](../guias/10-documentos-y-bpmn.md).

Actualizacion 2026-09-17: workers automaticos locales, analisis/transcripcion/indice
reales y CORS de Azure verificados. Grafo v2 con alternativas sustentadas y estados
de procesamiento integrados en el frontend. [Detalle actual](../guias/09-procesamiento-y-grafo-v2.md).

Fecha: 2026-09-16. Referencia: Plataforma_IA_Ensenanza_Producto_y_Roadmap.docx
entregado por el usuario. Se priorizan Teaching Agent, conocimiento gobernado y
recuperacion. No se implementan los prompts de diseno Figma del documento ni los
conectores SQL/WhatsApp; son vision futura, no pedidos de esta entrega.

## Requisitos y avance

- [x] Observar capturas y conversar por WebSocket autenticado, sin exponer keys.
- [x] Persistir texto del usuario, respuestas e idempotencia para reconectar.
- [x] Extraer frames y audio con limites; transcribir solo con consentimiento.
- [x] Incorporar transcripcion, notas y aclaraciones al analisis LangGraph.
- [x] Producir resumen, informe, instrucciones, dudas y referencias a fuentes.
- [x] Editar, responder dudas postanalisis, regenerar y conservar revisiones.
- [x] Exigir aprobacion humana antes de convertir o indexar el conocimiento.
- [x] Convertir a procedimiento borrador con evidencia y circuito de publicacion.
- [x] Recuperar trabajos por sesion; aislar fallos de analisis y de indexacion.
- [x] Preparar subidas por bloques, manifiesto y verificacion SHA-256.
- [x] Corregir reproduccion local y emitir SAS remoto inline sobre snapshot.
- [x] Indexar informes aprobados en pgvector y buscar con fuentes por tenant.
- [x] Devolver grafo secuencial del informe con referencias temporales.
- [x] Preparar variables en .env.example y .env sin credenciales ficticias activas.
- [x] Documentar cada nueva operacion HTTP y WebSocket.
- [ ] Probar proveedor OpenAI real y Azure real: faltan claves/configuracion.
- [ ] Acoplar frontend al socket, bloques, grafo y revision ampliada.
- [ ] Chat RAG redactado con citas/abstencion; indexar procedimientos solo textuales.
- [ ] Entidades de reglas de negocio, excepciones y ramificaciones editables.

Casilla completada significa logica implementada y pruebas locales indicadas;
no certifica disponibilidad de un servicio externo ni preparacion de produccion.

## Product backlog

| ID | Prioridad | Historia / criterio de aceptacion | Estado |
| --- | --- | --- | --- |
| VIS-01 | P0 | Experto conversa y muestra captura; permisos, limites y reintento sin duplicar | Backend probado, IA real pendiente |
| VIS-02 | P0 | Video/audio producen informe con notas y fuentes; sin consentimiento no se transcribe | Backend probado |
| VIS-03 | P0 | Usuario responde dudas y regenera conservando revision anterior | Backend probado |
| VIS-04 | P0 | Informe aprobado se convierte una vez a procedimiento publicable | Backend probado hasta publicacion |
| VIS-05 | P0 | Video local reproduce despues de detener captura | Corregido y probado en Edge |
| VIS-06 | P0 | Video remoto reproduce, permite buscar tiempo y renovar SAS | Logica lista, prueba Azure pendiente |
| VIS-07 | P1 | Reanudar bloques del mismo archivo tras recarga, sin duplicar reserva | Backend listo; frontend/servicio pendientes |
| VIS-08 | P1 | Buscar contenido aprobado por similitud con aislamiento por organizacion | pgvector real probado; embeddings reales pendientes |
| VIS-09 | P1 | Usuario ve pasos como grafico y abre instante de evidencia | Contrato listo; vista frontend pendiente |
| VIS-10 | P1 | Responder preguntas con citas y abstenerse sin evidencia | Pendiente, chat RAG |
| VIS-11 | P1 | Medir calidad/costo con video representativo y preguntas esperadas | Pendiente de ejemplo y cuota |
| VIS-12 | P1 | Retencion, borrado coordinado Blob/DB/vectores y auditoria operativa | Pendiente de politica |
| VIS-13 | P2 | Reglas, excepciones y ramas de proceso como entidades versionadas | Pendiente |
| VIS-14 | P2 | Importar Word/PDF para aprendizaje documental | Pendiente |
| VIS-15 | P2 | Voz en vivo con interrupciones y diarizacion temporal | Fuera de este incremento |

## Sprints

### Incremento implementado: logica backend

Objetivo: un video puede recorrer el pipeline de conocimiento validado sin que
las pruebas dependan de servicios de pago. Entregas VIS-01..09 en su alcance backend.
Verificacion: 47 tests backend, 18 frontend, build frontend y prueba de reproduccion
en navegador. Las migraciones se validaron primero en PostgreSQL aislado.

### Siguiente sprint propuesto: integracion real

Sin fechas comprometidas; depende de configuracion y disponibilidad del usuario.

1. Configurar claves, permisos, CORS, workers y origen HTTPS de pruebas.
2. Integrar componentes del frontend segun la guia visual.
3. Hacer captura real con audio, subida interrumpida, reanudacion y playback.
4. Evaluar analisis y preguntas; corregir/aprobar/convertir/publicar.
5. Confirmar indice, busqueda, fuentes, grafo y costo/latencia.

Cierre: flujo real repetible, sin secretos en navegador/logs, y pruebas de permiso,
token vencido, SAS vencido, fallo del proveedor y reinicio de worker.

### Sprint posterior propuesto: reutilizacion y gobierno

VIS-10..13: chat RAG con citas/abstencion, indexacion textual, retencion/borrado,
calidad, observabilidad y reglas de negocio. No introducir agentes autonomos ni
SQL productivo antes de completar validacion humana y limites operativos.

## Riesgos conocidos

- Muestreo cada 10 segundos puede omitir acciones; revisar incertidumbres.
- Audio y capturas pueden incluir datos sensibles: consentimiento y minimizacion.
- Consentimiento de captura no reemplaza politica empresarial de envio a OpenAI.
- Los snapshots conservan copias: definir retencion/costo antes de produccion.
- Limites por sesion no sustituyen cuotas distribuidas por tenant/cuenta.
- Grafo secuencial no representa automaticamente excepciones/decisiones.

[Credenciales y dependencias](lo-que-necesito.md) |
[Contratos frontend](../guias/06-aprendizaje-visual.md).
