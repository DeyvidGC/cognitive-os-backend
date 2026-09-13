# Orquestacion de Cognitive OS

LangGraph encaja con el aprendizaje porque permite estado persistente, pausas para
aclaraciones humanas y reanudacion. Esta entrega no lo instala ni ejecuta nodos
ficticios: implementa las operaciones persistentes que necesitara la orquestacion.

Propuesta:

1. Un worker reclama un job de PostgreSQL con bloqueo, lease y reintentos.
2. Un grafo recibe IDs autorizados de organizacion, sesion y job.
3. Los nodos cargan eventos/evidencias, llaman a un proveedor y validan respuestas
   estructuradas antes de construir un borrador.
4. El experto resuelve dudas y revisa. Aprobar requiere identidad y permisos del
   backend; una orden del modelo nunca sustituye esta autorizacion.
5. Otros trabajos generan tutoriales, embeddings e indices de la version aprobada.
6. La publicacion hace visible la version cuando sus derivados estan listos.

HTTP y transacciones editoriales quedan fuera del grafo. Modelos ORM representan
persistencia; schemas Pydantic representan contratos HTTP. Las respuestas de IA
tendran schemas propios y sus adaptadores iran en infrastructure/ai.
Los checkpoints seran persistentes, con thread_id definido por el servidor y
aislamiento por organizacion. No guardar credenciales ni sesiones SQLAlchemy en
el estado. Los efectos externos requieren idempotencia y limites de costo/reintentos.

Fuentes oficiales:
- https://docs.langchain.com/oss/python/langgraph/overview
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/interrupts
