# Arranque y error de deteccion de FastAPI

[Indice](../README.md)

## Diagnostico del 13 de septiembre

`Did not find a valid FastAPI app in main.py` no es un error de compilacion.
La importacion con `.venv` confirma que `main.app` es una instancia de FastAPI.
El archivo raiz reexporta la aplicacion creada por una factoria en
`src/cognitive_os/main.py`. La configuracion local de PyCharm es de tipo FastAPI
y apunta a ese archivo sin nombre explicito de aplicacion. Esto es consistente
con un fallo de deteccion del IDE, no con una aplicacion inexistente.

No se ha validado visualmente el boton Run del IDE. Se verifica el arranque real
con Python/Uvicorn y se entrega una configuracion que evita la autodeteccion.

## Arrancar en PyCharm

Seleccionar **Cognitive API (Uvicorn)** en las configuraciones de ejecucion.
La configuracion compartida [Cognitive API.run.xml](../../../.run/Cognitive%20API.run.xml)
usa el interprete `.venv/Scripts/python.exe`, la raiz como directorio de trabajo
y ejecuta el modulo `uvicorn` con `cognitive_os.main:app` como destino explicito.
No contiene contrasenas. La antigua configuracion **Cognitive** no se modifica.

Si no aparece, crear una configuracion de tipo **Python**, elegir **Module name**
`uvicorn`, parametros `cognitive_os.main:app --reload`, directorio raiz del proyecto
e interprete `.venv/Scripts/python.exe`.

## Arrancar desde PowerShell

Desde la raiz del proyecto, instalar las dependencias si aun no estan instaladas:

```powershell
.venv/Scripts/python.exe -m pip install -e '.[dev]'
.venv/Scripts/python.exe -m uvicorn cognitive_os.main:app --reload
```

Tambien funciona `.venv/Scripts/python.exe main.py` (sin recarga automatica).
La forma `-m uvicorn main:app` conserva compatibilidad.

Si 8000 esta ocupado, usar `--port 8001` en el comando de Uvicorn. No cerrar un
proceso ajeno para liberar el puerto. Abrir `/docs` en el puerto elegido.

## Separar los problemas

| Sintoma | Comprobacion |
| --- | --- |
| El IDE no detecta app | Usar la configuracion explicita anterior |
| No module named cognitive_os | Instalar el proyecto editable con el mismo interprete |
| No module named uvicorn | Instalar las dependencias del proyecto en .venv |
| Address already in use | Elegir otro puerto o detener tu servidor previo |
| Health funciona, los datos responden 503 | Revisar COGNITIVE_DATABASE_URL y migraciones |
| Conexion PostgreSQL rechazada | Revisar servicio, host, puerto y credenciales sin publicarlas |

La aplicacion no crea ni migra la base al arrancar. Un health 200 no demuestra
que PostgreSQL este conectado. Ver [configuracion y pruebas](02-probar-api.md).
