<<<<<<< HEAD
# 🚀 Ver 2 – Bot Meshtastic + Broker (Proyecto)

## 📌 Componentes incluidos
| Archivo | Función principal |
|---------|------------------|
| `Meshtastic_Relay.py` | Utilidades robustas para CLI Meshtastic (sync nodos, traceroute, vecinos, envío, CSV). |
| `Telegram_Bot_Broker_v2.2.py` | Bot de Telegram con menú, traceroute, telemetría, vecinos, broker, envío, estado. |
| `Meshtastic_Broker_v2.1.py` | Broker TCP local (JSONL) con heartbeats/estadísticas y extracción robusta de canal. |
| `broker_probe_v2.py` | Cliente de consola para escuchar el broker y resumir paquetes recibidos. |

--

## 🎯 1) Objetivo
Ecosistema integrado para operar una red **Meshtastic** desde **Telegram** y/o **consola**:

- 🤖 **Bot**: comandos para nodos, traceroute, telemetría, envío de mensajes, vecinos directos y escucha en tiempo real.
- 🔗 **Broker**: servidor local que difunde paquetes JSONL en tiempo real.
- ⚙️ **Relay**: capa portable que interactúa con la CLI Meshtastic.
- 📡 **Probe**: utilidad en consola para verificar el broker.

---

## ⚙️ 2) Requisitos

### 2.1 Software
- Python **3.10+** (probado con 3.11/3.12/3.13).
- CLI Meshtastic instalada y accesible:
  - Linux: `meshtastic` en PATH.
  - Windows: `%LOCALAPPDATA%\Programs\Python\Python313\Scripts\meshtastic.exe`
- Instalación de librerías:
  ```bash
  pip install -r requirements.txt
  ```

📦 `requirements.txt` incluye:
```
python-telegram-bot>=20.8,<22
meshtastic>=2.4.0
protobuf>=4.25.0
googleapis-common-protos>=1.63.0
paho-mqtt>=2.1.0
pyserial>=3.5
pubsub==1.0.2
```

### 2.2 Hardware
- Al menos **1 nodo Meshtastic accesible por TCP** (ej. `192.168.1.201`).
- Internet para el bot de Telegram.

---

## 📂 3) Estructura del proyecto
```
=======
Ver 2 – Bot Meshtastic + Broker (Proyecto)
Componentes incluidos
•	Meshtastic_Relay.py – Utilidades robustas para CLI Meshtastic (sync nodos, traceroute, vecinos, envío, CSV).
•	Telegram_Bot_Broker_v2.2.py – Bot de Telegram con menú, traceroute, telemetría, vecinos, broker, envío, estado.
•	Meshtastic_Broker_v2.1.py – Broker TCP local (JSONL) con heartbeats/estadísticas y extracción robusta de canal.
•	broker_probe_v2.py – Cliente de consola para escuchar el broker y resumir paquetes recibidos.
________________________________________
1) Objetivo
Esta V2 crea un ecosistema integrado para operar una red Meshtastic desde Telegram y/o consola:
•	Bot: comandos / menú para ver nodos, hacer traceroute, pedir telemetría, enviar mensajes (a nodo o broadcast), listar vecinos directos y escuchar en tiempo real vía broker.
•	Broker: servidor local que se conecta al nodo Meshtastic por TCP y difunde cada paquete recibido en JSON por línea (JSONL) a los clientes suscritos (bot, probe…).
•	Relay: capa portable que llama a la CLI de Meshtastic de forma segura y compatible en Windows/Linux (descubre automáticamente el ejecutable).
•	Probe: verificación rápida por consola de que el broker funciona y qué está recibiendo (canal, portnum, RSSI/SNR y texto si lo hay).
________________________________________
2) Requisitos
2.1. Software
•	Python 3.10+ (probado con 3.11/3.12/3.13).
•	CLI Meshtastic instalada y accesible:
o	Linux: normalmente meshtastic en PATH.
o	Windows: suele quedar en %LOCALAPPDATA%\Programs\Python\Python313\Scripts\meshtastic.exe (la V2 lo detecta automáticamente; aun así puedes fijar la ruta con MESHTASTIC_CLI_PATH o MESHTASTIC_EXE).
•	Bibliotecas Python (instalar con pip):
•	# requirements.txt (sugerido)
•	python-telegram-bot>=20.8,<22
•	meshtastic>=2.4.0
•	protobuf>=4.25.0
•	googleapis-common-protos>=1.63.0
•	paho-mqtt>=2.1.0           # (opcional, no requerido por defecto)
•	pyserial>=3.5              # (opcional, entornos específicos)
•	pubsub==1.0.2              # requerido por Meshtastic_Broker (pypubsub)
Nota: pubsub es pypubsub (en PyPI se instala con pip install pypubsub pero el paquete se importa como pubsub). Si al instalar aparece conflicto, prueba:
pip install pypubsub protobuf googleapis-common-protos python-telegram-bot meshtastic
2.2. Hardware/Conectividad
•	Al menos 1 nodo Meshtastic accesible por TCP (IP de tu nodo, p.ej. 192.168.1.201).
•	Conexión a Internet para el bot de Telegram.
________________________________________
3) Estructura del proyecto
>>>>>>> a289eac6868a7f1589e6a2fb314ce797fbd67906
.
├─ Meshtastic_Relay.py
├─ Telegram_Bot_Broker_v2.2.py
├─ Meshtastic_Broker_v2.1.py
├─ broker_probe_v2.py
├─ bot_data/
<<<<<<< HEAD
│   ├─ bot.log
│   ├─ stats.json
│   └─ nodos.txt
├─ salida_nodos.txt
├─ relay_nodes.csv
└─ requirements.txt
```

---

## 🔧 4) Variables de entorno

Ejemplo `.env`:
```bash
MESHTASTIC_HOST=xxx.xxx.xxx.xxx (IP DEL NODO MESHTASTIC)
MESHTASTIC_EXE=meshtastic
MESHTASTIC_BIND=127.0.0.1
MESHTASTIC_BRKPORT=8765

TELEGRAM_TOKEN=xxxxx:yyyyyy-zzzzz
ADMIN_IDS=123456789;987654321

BROKER_HOST=127.0.0.1
BROKER_PORT=8765
BROKER_CHANNEL=0
```

---

## ▶️ 5) Puesta en marcha

### 5.1 Broker
Linux/macOS:
```bash
python Meshtastic_Broker_v2.1.py --host $MESHTASTIC_HOST --bind 127.0.0.1 --port 8765 --verbose
```

Windows (PowerShell):
```powershell
python .\Meshtastic_Broker_v2.1.py --host $env:MESHTASTIC_HOST --bind 127.0.0.1 --port 8765 --verbose
```

### 5.2 Verificar broker
```bash
python broker_probe_v2.py --broker 127.0.0.1:8765 --dur 30 --canal 0
```

### 5.3 Bot de Telegram
```bash
python Telegram_Bot_Broker_v2.2.py
```

---

## 🤖 6) Uso del bot

### Menú principal
- 📡 Ver nodos
- 🧭 Traceroute
- 🛰️ Telemetría
- ✉️ Enviar mensaje
- 👂 Escuchar broker
- ⏹️ Parar escucha
- 👥 Vecinos directos
- ℹ️ Ayuda

### Comandos rápidos
```
/ver_nodos [N]
/traceroute !id
/telemetria !id
/enviar broadcast Hola red
/enviar !abcd1234 Hola nodo
/escuchar
/parar_escucha
/vecinos
/estado
/estadistica   # solo admin
```

---

## 💻 7) Uso desde consola (Relay)
Ejemplo:
```bash
python Meshtastic_Relay.py
# → "OK. Tabla guardada en salida_nodos.txt"
```

Funciones clave:
- `sincronizar_nodos_y_guardar()`
- `check_route_detallado(!id)`
- `send_test_message()`
- `export_csv()`

---

## 🔄 8) Flujo de datos
```
Nodo Meshtastic ⇄ Meshtastic_Broker ⇄ Bot Telegram / Probe
        ▲                ▲
        │ CLI (--nodes)  │ pubsub + TCP
        │                │
 Meshtastic_Relay.py     │
```

---

## 🛡️ 9) Buenas prácticas
- Usa `--ch-index` en vez de `--ch`.
- Archivos en **UTF-8**.
- Ajusta timeouts (`MESHTASTIC_TIMEOUT`, etc.).
- Logs:
  - Bot → `bot_data/bot.log`
  - Broker → consola
  - Relay → `relay_debug.log`

---

## 🖥️ 10) Ejecución como servicio
### Linux (systemd)
```ini
=======
│   ├─ bot.log          # log del bot
│   ├─ stats.json       # estadísticas de uso del bot
│   └─ nodos.txt        # cache último /nodes
├─ salida_nodos.txt     # tabla "meshtastic --nodes" (Relay)
├─ relay_nodes.csv      # exportaciones CSV (Relay)
└─ requirements.txt     # recomendado
________________________________________
4) Variables de entorno
Puedes usar un .env (o export/PowerShell) para configurar:
# Comunes
MESHTASTIC_HOST=192.168.1.201

# CLI Meshtastic (fallback en el bot y usado por el Relay)
MESHTASTIC_EXE=meshtastic           # o ruta completa
MESHTASTIC_CLI_PATH=                # alternativa en Relay, si quieres fijarla explícitamente

# Broker
MESHTASTIC_BIND=127.0.0.1
MESHTASTIC_BRKPORT=8765

# Bot Telegram
TELEGRAM_TOKEN=xxxxx:yyyyyy-zzzzz
# Lista de IDs admin separada por coma o punto y coma
ADMIN_IDS=123456789;987654321

# Tiempos (opcional)
MESHTASTIC_TIMEOUT=25
TRACEROUTE_TIMEOUT=35
TELEMETRY_TIMEOUT=30

# Bot: canal por defecto para /enviar (si no especificas otro)
BROKER_CHANNEL=0
BROKER_HOST=127.0.0.1
BROKER_PORT=8765
Windows (PowerShell):
setx TELEGRAM_TOKEN "xxxxx:yyyy" (reinicia la consola para que aplique).
________________________________________
5) Puesta en marcha
5.1. Broker (recomendado)
Inicia el broker para tener escucha en tiempo real y estadísticas:
Linux/macOS
python Meshtastic_Broker_v2.1.py --host $MESHTASTIC_HOST --bind 127.0.0.1 --port 8765 --verbose
Windows (PowerShell)
python .\Meshtastic_Broker_v2.1.py --host $env:MESHTASTIC_HOST --bind 127.0.0.1 --port 8765 --verbose
Verás algo como:
🟢 Broker v2.2 escuchando en 127.0.0.1:8765, conectando a 192.168.1.201 (verbose=True)
[RX Canal 0 | TEXT_MESSAGE_APP | !abcd1234 → !ffffffff] "Hola mundo"
ℹ️ Broker: heartbeat host=... stats={'total': 10, 'by_channel': {0: 10}}

5.2. Verificar broker por consola (opcional)
python broker_probe_v2.py --broker 127.0.0.1:8765 --dur 30 --canal 0
Salida de ejemplo:
📡 Conectando al broker en 127.0.0.1:8765 …
✅ Conectado.
🎧 Escuchando 30 s (canal: 0) …
[Canal 0 | TEXT_MESSAGE_APP | !abcd1234 → !ffffffff | RSSI -69 dBm | SNR 6.7 dB]
💬 Perfecto
⏹ Fin de la escucha.

📊 Resumen:
  Por portnum: TEXT_MESSAGE_APP:1
  Por canal  : 0:1

5.3. Bot de Telegram
python Telegram_Bot_Broker_v2.2.py
El bot:
•	Cargará el menú contextual oficial (SetMyCommands).
•	Usará Relay preferentemente para traceroute/nodes/telemetría/envío y broker para escuchar.
•	Guardará logs en ./bot_data/bot.log.
________________________________________
6) Uso del bot (comandos y menú)
•	/start o /menu → abre el menú principal:
o	📡 Ver últimos nodos: lee bot_data/nodos.txt o sincroniza por CLI.
o	🧭 Traceroute: solicita !id, devuelve saltos y ruta (A --> B --> C).
o	🛰️ Telemetría: solicita telemetría a !id con varias banderas (fallback).
o	✉️ Enviar mensaje: guiado con ForceReply (o usa la forma directa).
o	👂 Escuchar broker: suscribe el chat al broker para notificaciones en vivo.
o	⏹️ Parar escucha: quita la suscripción de este chat.
o	👥 Vecinos directos: lista nodos con 1 salto (traceroute por cada id).
o	ℹ️ Ayuda.

6.1. Comandos rápidos
•	/ver_nodos [N] – muestra últimos N (por defecto 20).
•	/traceroute !cdada0c1
•	/telemetria !cdada0c1
•	/enviar broadcast Mensaje a todos
•	/enviar !cdada0c1 Hola nodo!
•	/escuchar / /parar_escucha
•	/vecinos
•	/estado – estado rápido del host Meshtastic y del broker.
•	/estadistica – solo admin (usa ADMIN_IDS) muestra uso por usuario y por comando.
El bot trocea automáticamente las salidas largas (<pre>…</pre> HTML escapado) para evitar Message is too long.
________________________________________
7) Uso desde consola (relay)
El relay también puede usarse solo para sincronizar nodos:
python Meshtastic_Relay.py
# → "OK. Tabla guardada en salida_nodos.txt"
Funciones destacadas (internas):
•	sincronizar_nodos_y_guardar() → meshtastic --nodes en salida_nodos.txt.
•	get_visible_nodes_with_hops() → lee y ordena por “Since” y añade hops si existen en tabla.
•	check_route_detallado(!id) → (estado, hops, [ruta_ids], salida_bruta).
•	send_test_message(node_id|None, text, canal=0) → envío (broadcast si None).
•	export_csv(rows) → relay_nodes.csv con verificación.
________________________________________

8) Flujo de datos (alto nivel)
┌─────────────────┐     TCP        ┌────────────────────────┐      JSONL (push)
│ Nodo Meshtastic │ ◀────────────▶ │ Meshtastic_Broker v2.1 │ ────────────────▶ Clientes (Bot / Probe)
└─────────────────┘                 └────────────────────────┘
         ▲                                       ▲
         │ CLI (--nodes/--traceroute/--send…)    │ pubsub + TCPInterface
         │                                       │
      ┌───────────────┐                         ┌─────────────┐
      │ Meshtastic    │                         │ Telegram    │
      │ _Relay.py     │                         │ _Bot_ v2.2  │
      └───────────────┘                         └─────────────┘
•	El bot usa Relay para acciones “activas” (nodes/traceroute/telemetría/envío).
•	El bot se suscribe al broker para eventos RX en tiempo real.
•	broker_probe_v2.py permite verificar el broker sin el bot.
________________________________________
9) Buenas prácticas y consejos
•	Rutas ambiguas CLI: la V2 usa --ch-index cuando aplica para evitar ambigüedades (en Relay se corrige).
•	Encoding: todos los archivos se abren como UTF-8 con errors="ignore" para evitar charmap en Windows.
•	Timeouts: ajusta MESHTASTIC_TIMEOUT, TRACEROUTE_TIMEOUT, TELEMETRY_TIMEOUT si tu red es lenta.
•	Estadísticas bot: se guardan en bot_data/stats.json. No contienen datos sensibles; puedes limpiarlas si quieres.
•	Logs:
o	Bot → bot_data/bot.log
o	Broker (stdout/verbose) → consola / tu gestor de servicios
o	Relay → relay_debug.log
________________________________________





10) Ejecución como servicio
10.1. Linux (systemd)
Broker – /etc/systemd/system/meshtastic-broker.service
>>>>>>> a289eac6868a7f1589e6a2fb314ce797fbd67906
[Unit]
Description=Meshtastic Broker
After=network-online.target

[Service]
<<<<<<< HEAD
WorkingDirectory=/ruta/proyecto
ExecStart=/usr/bin/python3 Meshtastic_Broker_v2.1.py --host 192.168.1.201 --bind 127.0.0.1 --port 8765
=======
Type=simple
WorkingDirectory=/ruta/a/tu/proyecto
Environment="MESHTASTIC_HOST=192.168.1.201"
ExecStart=/usr/bin/python3 Meshtastic_Broker_v2.1.py --host ${MESHTASTIC_HOST} --bind 127.0.0.1 --port 8765
>>>>>>> a289eac6868a7f1589e6a2fb314ce797fbd67906
Restart=on-failure

[Install]
WantedBy=multi-user.target
<<<<<<< HEAD
```

### Windows (NSSM)
```powershell
nssm install MeshtasticBroker "C:\Path\to\python.exe" "C:\Path\to\Meshtastic_Broker_v2.1.py"
```

---

## 🛠️ 11) Solución de problemas
| Problema | Solución |
|----------|----------|
| ❌ `meshtastic` no encontrado | Ajustar `MESHTASTIC_EXE` o `MESHTASTIC_CLI_PATH` |
| ❗ Message is too long | Reducir N en `/ver_nodos` |
| ⚠️ charmap codec error | Regenerar archivos en UTF-8 |
| ⏱ Traceroute vacío | Aumentar `TRACEROUTE_TIMEOUT` |

---

## 🔑 12) Seguridad
- `ADMIN_IDS` controla acceso a `/estadistica`.
- Mantén tu **TELEGRAM_TOKEN** privado.
- Si el broker escucha en red, protégelo con firewall.

---

## 📌 13) Ejemplos rápidos
```bash
/ver_nodos 20
/vecinos
/traceroute !cdada0c1
/telemetria !cdada0c1
/enviar broadcast Atención pruebas
/escuchar
```

---

## 🤝 14) Contribución
- Probar siempre en **Windows** y **Linux**.
- Mantener formato JSON `{ "type":"packet","packet":{...} }`.

---

## 📄 15) Licencia
Licencia sugerida: **MIT**.

---

## ✅ 16) Checklist despliegue
- [ ] `pip install -r requirements.txt`
- [ ] Configurar variables de entorno
- [ ] Probar broker
- [ ] Probar probe
- [ ] Arrancar bot
- [ ] Ejecutar `/estado`, `/ver_nodos`, `/traceroute`
=======
Bot – /etc/systemd/system/meshtastic-bot.service
[Unit]
Description=Meshtastic Telegram Bot
After=network-online.target meshtastic-broker.service

[Service]
Type=simple
WorkingDirectory=/ruta/a/tu/proyecto
Environment="TELEGRAM_TOKEN=xxxxx:yyyy"
Environment="MESHTASTIC_HOST=192.168.1.201"
Environment="BROKER_HOST=127.0.0.1"
Environment="BROKER_PORT=8765"
ExecStart=/usr/bin/python3 Telegram_Bot_Broker_v2.2.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
Activar:
sudo systemctl daemon-reload
sudo systemctl enable --now meshtastic-broker.service
sudo systemctl enable --now meshtastic-bot.service

10.2. Windows (NSSM)
1.	Instala NSSM.
2.	Broker:
nssm install MeshtasticBroker "C:\Path\to\python.exe" "C:\Path\to\Meshtastic_Broker_v2.1.py" --host 192.168.1.201 --bind 127.0.0.1 --port 8765
3.	Bot:
nssm install MeshtasticBot "C:\Path\to\python.exe" "C:\Path\to\Telegram_Bot_Broker_v2.2.py"
Configura variables de entorno en la pestaña Environment o en el sistema.
________________________________________
11) Solución de problemas (FAQ)
1) ❗ No se encontró el ejecutable 'meshtastic'
•	Añade la CLI al PATH o define:
o	MESHTASTIC_EXE (bot) y/o
o	MESHTASTIC_CLI_PATH (relay) con ruta completa al ejecutable.
•	En Windows, la ruta típica es:
%LOCALAPPDATA%\Programs\Python\Python313\Scripts\meshtastic.exe
2) Message is too long en Telegram
•	La V2 ya trocea salidas y usa <pre> escapado. Si aún te ocurre, reduce N en /ver_nodos.
3) charmap codec… en nodos.txt o logs
•	La V2 abre en UTF-8 con tolerancia. Elimina archivos antiguos si siguen con encoding raro y deja que el bot/relay los regenere.
4) Traceroute/Telemetría no devuelven nada
•	Puede ser sin ruta o timeouts cortos. Sube TRACEROUTE_TIMEOUT / TELEMETRY_TIMEOUT.
•	En redes con pocos vecinos, envía antes un mensaje de “sondeo” para refrescar rutas:
•	/enviar !cdada0c1 Probando calidad de enlace...
•	/traceroute !cdada0c1
5) Broker arranca pero no ves tráfico
•	Usa broker_probe_v2.py sin filtro de canal:
python broker_probe_v2.py --broker 127.0.0.1:8765 --dur 60
•	Revisa que el nodo esté realmente recibiendo (proximidad, antena, canal correcto).
6) ExtBot.send_message was never awaited (PTB)
•	En V2 ya está resuelto (toda la E/S a Telegram es await y/o gestionada por el loop del Application).
7) Columnas / Hops en --nodes no cuadra
•	El parser del relay soporta cabeceras variables y detecta Hops cuando existe. Los vecinos directos por tabla se asumen hops=0 en tabla, mientras que traceroute considera 1 salto (origen → destino) como vecino directo.
________________________________________
12) Seguridad y roles
•	ADMIN_IDS controla quién puede ver /estadistica.
•	El bot no expone ninguna acción peligrosa; solo envía comandos Meshtastic y escucha broker.
•	Mantén tu TELEGRAM_TOKEN privado.
•	Si el broker se expone fuera de localhost, protégelo con firewall (recomendado 127.0.0.1).
________________________________________
13) Ejemplos rápidos
Ver 20 nodos y luego vecinos directos
/ver_nodos 20
/vecinos
Traceroute y telemetría
/traceroute !cdada0c1
/telemetria !cdada0c1
Enviar broadcast por canal configurado
/enviar broadcast Atención: pruebas en curso
Escuchar en tiempo real desde el broker
/escuchar
... (recibes "🔔 Broker: {...}" con cada paquete)
________________________________________


14) Contribución / mantenimiento
•	Asegúrate de probar en Windows y Linux si haces cambios en llamadas a la CLI.
•	Mantén nombres de funciones del Relay estables (el bot detecta varias variantes por compatibilidad).
•	Cualquier cambio en estructuras del broker: conserva {"type":"packet","packet":{...}} y añade campos en meta.
________________________________________
15) Licencia
Indica aquí la licencia del proyecto (p. ej. MIT, Apache-2.0, GPLv3…).
________________________________________
16) Checklist de despliegue
•	pip install -r requirements.txt
•	Configurar variables de entorno (TELEGRAM_TOKEN, MESHTASTIC_HOST, etc.)
•	Probar broker: Meshtastic_Broker_v2.1.py --verbose
•	Probar probe: broker_probe_v2.py --dur 15
•	Arrancar bot: Telegram_Bot_Broker_v2.2.py
•	Ejecutar /estado en Telegram
•	Ejecutar /ver_nodos y /traceroute !id
•	(Opcional) Instalar como servicio (systemd/NSSM)

>>>>>>> a289eac6868a7f1589e6a2fb314ce797fbd67906
