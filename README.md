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
.
├─ Meshtastic_Relay.py
├─ Telegram_Bot_Broker_v2.2.py
├─ Meshtastic_Broker_v2.1.py
├─ broker_probe_v2.py
├─ bot_data/
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
MESHTASTIC_HOST=192.168.1.201
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
[Unit]
Description=Meshtastic Broker
After=network-online.target

[Service]
WorkingDirectory=/ruta/proyecto
ExecStart=/usr/bin/python3 Meshtastic_Broker_v2.1.py --host 192.168.1.201 --bind 127.0.0.1 --port 8765
Restart=on-failure

[Install]
WantedBy=multi-user.target
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
