# Como mantener este registro

[Indice](README.md)

Al terminar una entrega, crear o ampliar bitacora/AAAA-MM-DD.md con la fecha real.
Si se retoma un dia despues, abrir otra entrada. Para reconstrucciones historicas,
identificar las fuentes y no inventar horas, commits o resultados.

Cada endpoint nuevo requiere una ficha con metodo/ruta, finalidad, permisos,
entrada, salida, efectos en SQL, errores y enlaces al codigo. Si cambia uno
existente, actualizar la ficha y registrar el antes/despues en la bitacora.
Revisar contratos.md contra schemas Pydantic y el OpenAPI del codigo.

Cada migracion nueva requiere actualizar el diccionario de tablas, relaciones y
estado aplicado/preparado. Un archivo SQL en Git no significa que se haya ejecutado.
Registrar por separado el estado de desarrollo, pruebas y base real.

Actualizar el indice y los diagramas cuando cambie el flujo. Verificar que los
enlaces relativos existan y que no haya endpoints sin ficha. No guardar secretos
ni ejemplos con credenciales reales. No marcar algo como automatico si necesita
un operador, una credencial, una extension o un worker que aun no existe.

Este documento es una convencion manual de trabajo, no un generador ni una tarea
programada. Las fichas actuales se construyeron contrastando codigo y OpenAPI.
