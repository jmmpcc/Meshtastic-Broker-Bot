# Telegram Bot Broker · v2.3

Este repositorio contiene la versión 2.3 de **Telegram Bot Broker**, un bot de Telegram para interactuar con tu red Meshtastic a través de un broker MQTT/HTTP, con soporte para CLI y Meshtastic Relay.

---

## 🚀 Novedades en v2.3

1. **Listado numerado de nodos**  
   `/ver_nodos [N]` muestra los últimos _N_ nodos vistos (por defecto 20), con formato:  
   ```
   1. Alias (ID) — visto hace 0 min — hops: 2  
   2. OtroNodo (ID) — visto hace 1 min  
   …
   ```

2. **Selección por índice en todos los comandos**  
   Cualquiera de los comandos que antes recibían `!ID` acepta ahora el número de la lista:  
   ```bash
   /traceroute 3      # igual que /traceroute !abcd1234  
   /telemetria 1  
   /enviar 2 Hola  
   /vecinos 5  
   ```

3. **`/telemetria` reparado**  
   Ahora siempre invoca el CLI con `--dest <ID> --request-telemetry` para evitar el warning:  
   ```
   Warning: Must use a destination node ID.
   ```

4. **Escucha selectiva de canales**  
   `/escuchar [canal|all]`:  
   - Sin argumentos → canal por defecto.  
   - `/escuchar 5` → solo canal 5.  
   - `/escuchar all` (o `*`) → todos los canales.  

   Solo reenvía **TEXT_MESSAGE_APP** (mensajes de texto) y muestra el canal de llegada.

5. **`/parar_escucha`**  
   Detiene la escucha activa en el broker y libera recursos.

6. **Ayuda actualizada**  
   `/ayuda` incluye todos los comandos, opciones y ejemplos de uso.

7. **Compatibilidad full CLI & Relay**  
   Se fuerza el fetch de nodos vía Meshtastic Relay con fallback a CLI, y luego parseo con extracción de hops.

---

## 📦 Instalación y Dependencias

1. Clona el repositorio:  
   ```bash
   git clone https://github.com/tu_usuario/telegram-bot-broker.git
   cd telegram-bot-broker
   git checkout v2.3
   ```

2. Entorno:  
   - Python 3.9+  
   - Dependencias (requirements.txt o virtualenv):  
     ```
     python-telegram-bot>=20.0
     paho-mqtt
     meshtastic
     ```

3. Configura variables en el entorno o en el script:  
   ```bash
   export BROKER_HOST=127.0.0.1
   export BROKER_PORT=8765
   export BROKER_CHANNEL=0
   export MESHTASTIC_HOST=192.168.1.201
   ```

4. Asegúrate de que `Meshtastic_Relay.py` esté en la misma carpeta (o en tu PYTHONPATH) y exporte:  
   - `_parse_nodes_table`  
   - `parse_minutes`  
   - `_to_int_safe`  
   - `sync_nodes_and_save`  
   - `NODES_FILE`

---

## 🛠️ Uso

### Levantar el bot
```bash
python telegram_bot_broker_v2.3.py
```
Verás en logs:
```
🤖 Bot arrancado y listo. Menú establecido.
```

### Comandos principales

| Comando                          | Descripción                                                                                     |
|----------------------------------|-------------------------------------------------------------------------------------------------|
| `/ver_nodos [N]`                 | Lista los últimos _N_ nodos (predet. 20), numerados con “visto hace X min” y “hops: Y”.         |
| `/traceroute <n|!id>`            | Muestra la ruta completa hacia el nodo (usa índice o ID).                                       |
| `/telemetria <n|!id>`            | Solicita telemetría (CLI con `--dest`, sin warnings).                                           |
| `/enviar <n|!id|broadcast> texto`| Envía un mensaje de texto al nodo o a todos (`broadcast`).                                      |
| `/escuchar [canal|all]`          | Escucha **solo** mensajes de texto entrantes por el broker.                                     |
| `/parar_escucha`                 | Detiene la escucha activa en el broker.                                                         |
| `/vecinos <n|!id>`               | Muestra vecinos directos (1 salto) del nodo.                                                    |
| `/estado`                        | Comprueba el estado del broker y del bot.                                                       |
| `/estadistica`                   | (Admin) Muestra estadísticas de uso del bot.                                                    |
| `/ayuda`                         | Muestra esta ayuda.                                                                             |

---

## 🔄 Actualización desde v2.2

1. Crea o cámbiate a la rama `v2.3` y asegúrate de que tu script principal es `telegram_bot_broker_v2.3.py`.  
2. Verifica en los imports que `Meshtastic_Relay.py` exporta los nuevos helpers:
   ```python
   from Meshtastic_Relay import (
       _parse_nodes_table,
       parse_minutes,
       _to_int_safe,
       sync_nodes_and_save,
       NODES_FILE
   )
   ```
3. Actualiza dependencias si es necesario:
   ```bash
   pip install --upgrade python-telegram-bot meshtastic paho-mqtt
   ```
4. Reinicia el bot y prueba `/ver_nodos`, `/telemetria`, `/escuchar`, etc.

---

## ⚙️ Consideraciones Especiales

- El usuario que arranca el bot debe tener acceso al host Meshtastic (puerto configurado).  
- Si `Meshtastic_Relay.py` está en otro directorio, ajusta tu PYTHONPATH o usa imports relativos.  
- `BrokerClient` se recrea automáticamente si cambias de canal con `/escuchar`.
