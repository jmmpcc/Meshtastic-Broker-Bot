#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meshtastic_Broker v2.2 – Broker local (JSONL) con:
- Serialización robusta (protobuf → dict, bytes → hex).
- 'packet.meta.channelIndex' siempre presente (extracción robusta snake/camel).
- Heartbeats cada 5 s con estadísticas {total, by_channel}.
- "Priming" periódico para que los clientes vean vida.
- Modo verboso (--verbose) con resumen por paquete.

Protocolo de salida a clientes: JSON por línea (UTF-8).
  - {"type":"packet","packet":{...}}
  - {"type":"status","msg":"connected|heartbeat|priming|...","host": "...", "stats": {...}}
  - {"type":"broker_info","msg":"connected"} (al conectar un cliente)

Uso:
    python Meshtastic_Broker.py --host 192.168.1.201 --bind 127.0.0.1 --port 8765 --verbose

Variables de entorno:
    MESHTASTIC_HOST, MESHTASTIC_BIND, MESHTASTIC_BRKPORT
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import socketserver
import threading
import time
from typing import Any, Dict, List, Optional

from pubsub import pub
import meshtastic
import meshtastic.tcp_interface
from meshtastic.mesh_interface import MeshInterface  # type: ignore
MeshInterfaceError = getattr(MeshInterface, "MeshInterfaceError", Exception)  # type: ignore

# ---- protobuf a dict (siempre presente en entornos Meshtastic) ----
try:
    from google.protobuf.message import Message as _PBMessage  # type: ignore
    from google.protobuf.json_format import MessageToDict  # type: ignore
except Exception:
    _PBMessage = tuple()  # type: ignore
    def MessageToDict(msg, preserving_proto_field_name=True):  # type: ignore
        return {"_proto_repr": str(msg)}

# ------------------------------ Config ------------------------------

DEFAULT_HOST = os.getenv("MESHTASTIC_HOST", "192.168.1.201")
DEFAULT_BIND = os.getenv("MESHTASTIC_BIND", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("MESHTASTIC_BRKPORT", "8765"))

# ----------------------- Estado global broker -----------------------

_clients_lock = threading.Lock()
_clients: List[socket.socket] = []

_interface_lock = threading.Lock()
_interface: Optional[meshtastic.tcp_interface.TCPInterface] = None
_should_run = True

_stats_lock = threading.Lock()
_total_packets = 0
_by_channel: Dict[int, int] = {}

_verbose = False
_last_priming = 0.0

# --------------------------- Serialización --------------------------

def _sanitize(obj: Any) -> Any:
    """
    Convierte recursivamente a tipos JSON-serializables:
    - bytes/bytearray → hex
    - protobuf Message → dict (MessageToDict, preserva nombres snake_case)
    - dict/list/tuple/set → saneado elemento a elemento
    - float NaN/Inf → None (JSON válido)
    - objetos con __dict__ → vars(obj) saneado
    """
    if isinstance(obj, (bytes, bytearray)):
        return obj.hex()
    if _PBMessage and isinstance(obj, _PBMessage):
        try:
            return _sanitize(MessageToDict(obj, preserving_proto_field_name=True))
        except Exception:
            return {"_proto_repr": str(obj)}
    if isinstance(obj, dict):
        return {str(_sanitize(k)): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if hasattr(obj, "__dict__") and not isinstance(obj, (str, int, float, bool, type(None))):
        try:
            return _sanitize(vars(obj))
        except Exception:
            return str(obj)
    return obj

def _safe_json_dumps(obj: Any) -> str:
    """Serializa a JSON aplicando saneo profundo. Siempre devuelve una cadena JSON válida."""
    try:
        return json.dumps(_sanitize(obj), ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        return json.dumps({"type": "status", "msg": f"serialization_error: {e}"}, ensure_ascii=False)

# --------------------------- Utilidades -----------------------------

def _safe_send_line(sock: socket.socket, line: str) -> bool:
    """Envía una línea UTF-8 terminada en '\\n'. Devuelve False si el envío falla."""
    try:
        data = (line.rstrip("\n") + "\n").encode("utf-8", errors="replace")
        sock.sendall(data)
        return True
    except Exception:
        return False

def _broadcast_json(obj) -> None:
    """Difunde un objeto a todos los clientes (JSONL). Elimina desconectados."""
    line = _safe_json_dumps(obj)
    drop: List[socket.socket] = []
    with _clients_lock:
        for s in _clients:
            if not _safe_send_line(s, line):
                drop.append(s)
        for d in drop:
            try:
                _clients.remove(d)
                d.close()
            except Exception:
                pass

def _get(d: dict, path: str, default=None):
    """Acceso seguro por ruta tipo 'a.b.c'."""
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

# ------------------ Extracción robusta de canal ---------------------

def _extract_channel(pkt: dict) -> Optional[int]:
    """
    Devuelve el índice de canal buscando múltiples rutas snake/camel:
      decoded.header.channelIndex / decoded.header.channel_index
      rxMetadata.channel / rx_metadata.channel
      decoded.channel / decoded.channel_index
    """
    candidates = [
        "decoded.header.channelIndex",
        "decoded.header.channel_index",
        "rxMetadata.channel",
        "rx_metadata.channel",
        "decoded.channel",
        "decoded.channel_index",
    ]
    for path in candidates:
        v = _get(pkt, path)
        if isinstance(v, int):
            return v
    return None

def _packet_summary(pkt: dict) -> str:
    """Resumen humano del paquete para --verbose."""
    dec = pkt.get("decoded", {}) or {}
    hdr = dec.get("header", {}) or {}
    data = dec.get("data", {}) or {}
    ch = pkt.get("meta", {}).get("channelIndex", _extract_channel(pkt))
    frm = hdr.get("fromId", ""); to = hdr.get("toId", "")
    port = dec.get("portnum"); txt = data.get("text", None)
    rssi = pkt.get("rssi"); snr = pkt.get("rxSnr")
    head = f"RX Canal {ch if ch is not None else '??'} | {port or 'UNKNOWN'} | {frm} → {to or '?'}"
    if txt is not None:
        return f'{head} | "{txt}"'
    extras = []
    if rssi is not None: extras.append(f"RSSI {rssi} dBm")
    if snr  is not None: extras.append(f"SNR {snr} dB")
    return f"{head} (no-texto){(' | ' + ' | '.join(extras)) if extras else ''}"

def _inc_stats_from_packet(pkt: dict) -> None:
    """Incrementa contadores globales y por canal usando el mismo extractor robusto."""
    global _total_packets
    ch = pkt.get("meta", {}).get("channelIndex", _extract_channel(pkt))
    with _stats_lock:
        _total_packets += 1
        if isinstance(ch, int):
            _by_channel[ch] = _by_channel.get(ch, 0) + 1

def _get_stats() -> dict:
    """Snapshot de contadores para heartbeats."""
    with _stats_lock:
        return {"total": _total_packets, "by_channel": dict(_by_channel)}

# ------------------------- Servidor TCP -----------------------------

class BrokerTCPHandler(socketserver.BaseRequestHandler):
    """
    Maneja clientes TCP en modo push (solo salida). Al conectar:
      -> envía {"type":"broker_info","msg":"connected"}
    """
    def handle(self):
        sock = self.request
        with _clients_lock:
            _clients.append(sock)
        _safe_send_line(sock, _safe_json_dumps({"type": "broker_info", "msg": "connected"}))
        try:
            while True:
                data = sock.recv(1024)
                if not data:
                    break  # ignoramos la entrada; protocolo push
        except Exception:
            pass
        finally:
            with _clients_lock:
                try:
                    _clients.remove(sock)
                except ValueError:
                    pass
            try:
                sock.close()
            except Exception:
                pass

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

# ---------------------- Gestión de TCPInterface ---------------------

def _pubsub_callback(packet: dict, interface) -> None:
    """
    Recibe cada paquete RX desde 'meshtastic.receive', añade meta.channelIndex,
    actualiza contadores y difunde a clientes como {"type":"packet"}.
    """
    try:
        ch = _extract_channel(packet)
        if "meta" not in packet or not isinstance(packet["meta"], dict):
            packet["meta"] = {}
        packet["meta"]["channelIndex"] = ch

        _inc_stats_from_packet(packet)

        if _verbose:
            print(_packet_summary(packet), flush=True)

        _broadcast_json({"type": "packet", "packet": packet})
    except Exception as e:
        if _verbose:
            print(f"[broker] error en _pubsub_callback: {e}", flush=True)

def _priming_tick(host: str):
    """
    Heartbeat/priming cada ~60 s. No 'despierta' nada en la interfaz, pero
    sirve para que clientes vean actividad y métricas aunque no haya RF.
    """
    global _last_priming
    now = time.time()
    if now - _last_priming < 60:
        return
    _last_priming = now
    _broadcast_json({"type": "status", "msg": "priming", "host": host, "stats": _get_stats()})

def _connect_interface_loop(host: str):
    """
    Mantiene la TCPInterface conectada con reintentos y envía heartbeats cada 5 s.
    """
    global _interface
    last_hb = 0.0
    while _should_run:
        try:
            with _interface_lock:
                if _interface is None:
                    if _verbose:
                        print(f"[broker] conectando a {host}…", flush=True)
                    _interface = meshtastic.tcp_interface.TCPInterface(hostname=host)
                    pub.subscribe(_pubsub_callback, "meshtastic.receive")
                    _broadcast_json({"type": "status", "msg": "connected", "host": host})
                    if _verbose:
                        print(f"[broker] conectado a {host}", flush=True)

            now = time.time()
            if now - last_hb >= 5.0:
                _broadcast_json({"type": "status", "msg": "heartbeat", "host": host, "stats": _get_stats()})
                last_hb = now

            _priming_tick(host)
            time.sleep(0.5)

        except MeshInterfaceError as e:
            _broadcast_json({"type": "status", "msg": f"connect_error: {e}"})
            if _verbose:
                print(f"[broker] connect_error: {e}", flush=True)
            time.sleep(3.0)
        except Exception as e:
            _broadcast_json({"type": "status", "msg": f"unexpected_error: {e}"})
            if _verbose:
                print(f"[broker] unexpected_error: {e}", flush=True)
            time.sleep(3.0)

def _close_interface():
    """Cierra interfaz TCP y anula la suscripción al bus pubsub."""
    global _interface
    with _interface_lock:
        if _interface:
            try:
                pub.unsubscribe(_pubsub_callback, "meshtastic.receive")
            except Exception:
                pass
            try:
                _interface.close()
            except Exception:
                pass
            _interface = None

# ------------------------------ Main --------------------------------

def main():
    parser = argparse.ArgumentParser(description="Broker local Meshtastic (v2.2, meta.channelIndex)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="IP del nodo Meshtastic")
    parser.add_argument("--bind", default=DEFAULT_BIND, help="IP local para escuchar el broker")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Puerto TCP del broker")
    parser.add_argument("--verbose", action="store_true", help="Imprime cada paquete RX y eventos")
    args = parser.parse_args()

    global _verbose
    _verbose = bool(args.verbose)

    server = ThreadedTCPServer((args.bind, args.port), BrokerTCPHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    threading.Thread(target=_connect_interface_loop, args=(args.host,), daemon=True).start()

    print(f"🟢 Broker v2.2 escuchando en {args.bind}:{args.port}, conectando a {args.host} (verbose={_verbose})")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        global _should_run
        _should_run = False
        _close_interface()
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass
        print("⏹ Broker detenido.")

if __name__ == "__main__":
    main()
