# Frontend Vercel con backend local

Frontend: https://cognitive-os-frontend.vercel.app

El backend ya permite ese origen exacto mediante COGNITIVE_CORS_ORIGINS en .env
y .env.example, conservando localhost:5173. Reiniciar la API para cargar el cambio.
La lista tambien autoriza el Origin del WebSocket; no se habilito comodin *.vercel.app.

## Opcion A: probar desde la misma computadora

1. Ejecutar Cognitive desde PyCharm Run, puerto 8000. Mantenerlo abierto.
2. Abrir http://127.0.0.1:8000/api/v1/health y comprobar status:ok.
3. En Vercel, proyecto del frontend > Settings > Environment Variables, configurar
   VITE_API_BASE_URL con valor http://127.0.0.1:8000/api/v1 para Production.
4. Hacer un nuevo deployment/redeploy: Vite incorpora esta variable al compilar;
   no basta con modificarla y recargar un despliegue anterior.
5. Abrir el frontend desde esta misma PC. Si el navegador solicita acceso a la
   red local, permitirlo para este sitio de confianza. No desactivar seguridad web.

localhost pertenece a la computadora del visitante. Esta opcion NO permite que
un amigo o un celular se conecte a tu backend: intentaria su propio localhost.
Tampoco funciona poner localhost como destino de un proxy ejecutado en Vercel.
El acceso HTTP local desde HTTPS depende de permisos/politicas del navegador;
si se bloquea, o para probar WSS de forma consistente, usar la opcion B.

No cambiar API_PROXY_TARGET en Vercel esperando que haga un tunel: esa variable
configura el servidor de desarrollo Vite, que no se ejecuta en el sitio estatico.
No poner /api/v1 solamente en Vercel sin un proxy real: apuntaria al propio frontend.

## Opcion B: tunel HTTPS temporal

Util para una demostracion compartida y para evitar dependencias del acceso a red
local del navegador. Expone tu API a Internet mientras este abierto. No se inicio
automaticamente un tunel ni se modifico la cuenta de Vercel en esta entrega.

1. Usar una base de pruebas sin informacion sensible y cuentas de demostracion.
   Antes de exponer la API, configurar COGNITIVE_REGISTRATION_ENABLED=false y
   reiniciar, si ya tienes tu cuenta creada. CORS no sustituye autenticacion ni cuotas.
2. Instalar cloudflared desde la distribucion oficial de Cloudflare.
3. Mantener la API escuchando solamente en 127.0.0.1:8000. No abrir el puerto 5432
   de PostgreSQL ni hacer port forwarding en el router.
4. En otra consola ejecutar:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

5. El comando imprime una URL HTTPS temporal. Comprobar SU_URL/api/v1/health.
6. En Vercel configurar VITE_API_BASE_URL=SU_URL/api/v1 y volver a desplegar.
   SU_URL debe reemplazarse por el dominio real, sin comillas ni Markdown.
7. Mantener ambos procesos encendidos. Ctrl+C al terminar la demostracion.

La URL Quick Tunnel puede cambiar al reiniciar: actualizar Vercel y redeploy.
Para uso estable, desplegar el backend o configurar un tunel con hostname fijo.
Los Quick Tunnels son para pruebas, no produccion, y no soportan SSE; el agente
actual utiliza WebSocket, no SSE. La construccion del socket debe derivar la misma
base de API y convertir https a wss; no dejar localhost hardcodeado en el frontend.

## Azure y workers

Para subir/reproducir videos desde Vercel tambien se necesita CORS en Blob Storage,
independiente del CORS de FastAPI. Con las credenciales configuradas:

```powershell
.venv/Scripts/python.exe -m cognitive_os.infrastructure.storage.setup_azure --origin https://cognitive-os-frontend.vercel.app
```

Los workers de analisis e indexacion deben continuar ejecutandose en tu PC.
Apagar la computadora detiene API, tunel y workers. Las API keys y la conexion DB
permanecen en .env del backend, nunca en variables VITE_*.

## Diagnostico

| Sintoma | Revisar |
| --- | --- |
| 404 o HTML en /api/v1/auth/login | Base URL relativa apuntando a Vercel; variable y redeploy |
| ERR_CONNECTION_REFUSED | API apagada o puerto equivocado |
| Bloqueo CORS | Origen exacto sin barra final y reinicio del backend |
| Bloqueo de red local/contenido mixto | Permiso del navegador o tunel HTTPS; no desactivar seguridad |
| 401 | Conexion funciona; revisar sesion/credenciales |
| 503 de almacenamiento/IA | Conexion funciona; faltan claves o proveedor disponible |
| Jobs pending | Worker detenido, no problema de CORS |
| Falla subida a Blob | CORS de Azure, SAS vencido o encabezados incorrectos |

Validacion de esta entrega: pruebas locales de preflight GET/POST, Authorization,
X-Organization-ID, Content-Type, health y rechazo de origen no permitido. No se
afirma que el despliegue Vercel ya haya sido reconfigurado o probado extremo a extremo.

Referencias: [Vite: variables de entorno](https://vite.dev/guide/env-and-mode),
[Vercel: variables](https://vercel.com/docs/environment-variables),
[Chrome: acceso a red local](https://developer.chrome.com/blog/local-network-access),
[Cloudflare: Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).
