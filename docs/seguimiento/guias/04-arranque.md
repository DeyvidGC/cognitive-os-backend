# Arranque y error de deteccion de FastAPI

[Indice](../README.md)

## Diagnostico del 13 de septiembre

`Did not find a valid FastAPI app in main.py` no es un error de compilacion.
La importacion con `.venv` confirma que `main.app` es una instancia de FastAPI.
El archivo raiz originalmente reexportaba la aplicacion creada por una factoria en
`src/cognitive_os/main.py`. La configuracion local de PyCharm es de tipo FastAPI
y apunta a ese archivo sin nombre explicito de aplicacion. Esto es consistente
con un fallo de deteccion del IDE, no con una aplicacion inexistente.

No se ha validado visualmente el boton Run del IDE. Se verifica el arranque real
con Python/Uvicorn y se entrega una configuracion que evita la autodeteccion.

## Arrancar en PyCharm

### Conservar la configuracion FastAPI Cognitive de tu captura

No hace falta ejecutar un comando ni depender del bloque `if __name__`.
En **Run > Edit Configurations > FastAPI > Cognitive**, dejar estos valores:

| Campo visible | Valor |
| --- | --- |
| Application file | `C:/Users/deyvi/PycharmProjects/Cognitive/main.py` |
| Application name | `app` (sin comillas, no `main:app`) |
| Run using | Uvicorn |
| Run options | `--reload --host 127.0.0.1 --port 8000` |
| Python interpreter | `C:/Users/deyvi/PycharmProjects/Cognitive/.venv/Scripts/python.exe` |
| Working directory | `C:/Users/deyvi/PycharmProjects/Cognitive` |

En la captura, **Application name** esta en `<detect automatically>` y
**Working directory** esta vacio. Escribir `app` en el primero y la raiz del
proyecto en el segundo. Pulsar **Apply**, luego **OK**, dejar **Cognitive**
seleccionado arriba y pulsar el triangulo verde **Run**.

Abrir [Swagger](http://127.0.0.1:8000/docs) para ver y probar la API. Run inicia
el servidor; esta configuracion no promete abrir automaticamente el navegador.
Si aparece un conflicto de puerto, detener tu ejecucion anterior desde su boton
Stop o cambiar el puerto a 8001 y abrir http://127.0.0.1:8001/docs.

El main.py raiz ahora crea la unica instancia global con `app = create_app()`.
La factoria interna conserva rutas, middleware, errores y lifespan de PostgreSQL.
Se retiro el bloque `if __name__ == "__main__"`: PyCharm/Uvicorn importa `app`
y administra el servidor. Ejecutar main.py como un script Python normal ya no
levanta un servidor; usar la configuracion FastAPI **Cognitive** o la alternativa
compartida de Uvicorn. Mantener **Application name = app** evita autodeteccion.

Estos cambios deben confirmarse en el dialogo abierto del IDE: no se edita
`.idea/workspace.xml` por detras mientras PyCharm lo mantiene en memoria, ni se
afirma haber pulsado Run. La captura permite identificar los campos necesarios.

### Alternativa compartida ya incluida

Seleccionar **Cognitive API (Uvicorn)** en las configuraciones de ejecucion.
La configuracion compartida [Cognitive API.run.xml](../../../.run/Cognitive%20API.run.xml)
usa el interprete `.venv/Scripts/python.exe`, la raiz como directorio de trabajo
y ejecuta el modulo `uvicorn` con `main:app` como destino explicito.
No contiene contrasenas. La antigua configuracion **Cognitive** no se modifica.

Si no aparece, crear una configuracion de tipo **Python**, elegir **Module name**
`uvicorn`, parametros `main:app --reload`, directorio raiz del proyecto
e interprete `.venv/Scripts/python.exe`.

## Arrancar desde PowerShell

Desde la raiz del proyecto, instalar las dependencias si aun no estan instaladas:

```powershell
.venv/Scripts/python.exe -m pip install -e '.[dev]'
.venv/Scripts/python.exe -m uvicorn main:app --reload
```

El punto de entrada unico es `main:app`; el modulo interno contiene solamente
la factoria y ya no expone una segunda instancia global.

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
