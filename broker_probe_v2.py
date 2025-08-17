#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broker_probe_v2.py — Probe del broker con extracción de texto desde payload
y detección robusta de canal. Resume por portnum y canal al final.

Funciones (resumen):
- parse_broker_addr(addr): host,port desde "host:puerto".
- open_broker(addr, timeout): abre socket TCP con timeouts breves.
- read_jsonl_lines(sock, until_ts, canal): lee JSONL, filtra y muestra.
- extract_channel(pkt): intenta obtener channelIndex de varios lugares.
- try_get_text(pkt): intenta recuperar texto de decoded.data.text o payloads.
- summarize_packet(pkt): una línea amigable con canal/portnum/from→to, RSSI/SNR y texto si hay.
"""

from __future__ import annotations
import argparse
import json
import os
import socket
import time
from typing import Optional, Tuple, Dict, Any

STATS_PORT: Dict[str, int] = {}
STATS_CH: Dict[str, int] = {}

def parse_broker_addr(addr: str) -> Tuple[str, int]:
    host, port = addr.split(":", 1)
    return host, int(port)

def open_broker(addr: str, timeout: float = 5.0) -> socket.socket:
    host, port = parse_broker_addr(addr)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    s.settimeout(0.5)
    return s

def _get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def extract_channel(pkt: dict) -> Optional[int]:
    """
    Intenta deducir el canal de múltiples ubicaciones posibles.
    """
    # 1) Habitual
    ch = _get(pkt, "decoded.header.channelIndex")
    if isinstance(ch, int):
        return ch
    # 2) Algunos payloads
    ch = _get(pkt, "rxMetadata.channel")
    if isinstance(ch, int):
        return ch
    ch = _get(pkt, "decoded.channel")
    if isinstance(ch, int):
        return ch
    # 3) Nada fiable
    return None

def _looks_text(b: bytes) -> bool:
    """
    Heurística sencilla: bytes parecen texto UTF-8 si decodifican y son mayormente imprimibles.
    """
    try:
        s = b.decode("utf-8")
    except Exception:
        return False
    # porcentaje de imprimibles
    printable = sum(1 for c in s if (c.isprintable() or c in "\r\n\t"))
    return (printable / max(1, len(s))) > 0.9

def try_get_text(pkt: dict) -> Optional[str]:
    """
    Intenta recuperar texto del paquete:
    1) decoded.data.text (camino normal)
    2) decoded.payload (hex) → si se recibió del broker v2.1 en hex
    3) decoded.raw / request / dataPayload (hex) → casos alternativos
    """
    # 1) Normal
    txt = _get(pkt, "decoded.data.text")
    if isinstance(txt, str):
        return txt

    # 2) Intentar payloads hex -> bytes -> utf-8
    candidates = [
        "decoded.payload",
        "decoded.data.payload",
        "payload",
        "request",
        "dataPayload",
        "decoded.request",
    ]
    for path in candidates:
        val = _get(pkt, path)
        if isinstance(val, str):
            # ¿hex?
            try:
                b = bytes.fromhex(val)
            except Exception:
                continue
            if _looks_text(b):
                try:
                    return b.decode("utf-8")
                except Exception:
                    continue
    return None

def summarize_packet(pkt: dict) -> str:
    dec = pkt.get("decoded", {}) or {}
    hdr = dec.get("header", {}) or {}
    data = dec.get("data", {}) or {}

    port = dec.get("portnum")
    frm = hdr.get("fromId", "")
    to  = hdr.get("toId", "")

    ch = extract_channel(pkt)
    rssi = pkt.get("rssi")
    snr  = pkt.get("rxSnr")

    head_parts = [f"Canal {ch if ch is not None else '??'}", f"{port or 'UNKNOWN'}", f"{frm} → {to or '?'}"]
    if rssi is not None:
        head_parts.append(f"RSSI {rssi} dBm")
    if snr is not None:
        head_parts.append(f"SNR {snr} dB")
    head = " | ".join(head_parts)

    txt = try_get_text(pkt)
    if txt is not None:
        return f"[{head}]\n💬 {txt}"
    return f"[{head}] (no-texto)"

def handle_broker_message(obj: dict, canal_filter: Optional[int]) -> bool:
    t = obj.get("type")
    if t in ("status", "broker_info"):
        msg = obj.get("msg", "")
        host = obj.get("host", "")
        # stats opcionales
        stats = obj.get("stats")
        if stats:
            print(f"ℹ️ Broker: {t} {msg} {host} {stats}")
        else:
            print(f"ℹ️ Broker: {t} {msg} {host}".strip())
        return False

    if t != "packet":
        return False

    pkt = obj.get("packet", {})
    ch = extract_channel(pkt)
    if canal_filter is not None and ch != canal_filter:
        return False

    # contadores
    port = _get(pkt, "decoded.portnum") or "UNKNOWN"
    STATS_PORT[port] = STATS_PORT.get(port, 0) + 1
    key_ch = str(ch) if ch is not None else "None"
    STATS_CH[key_ch] = STATS_CH.get(key_ch, 0) + 1

    print(summarize_packet(pkt))
    return True

def read_jsonl_lines(sock: socket.socket, until_ts: float, canal: Optional[int]) -> int:
    buf = b""
    count = 0
    while time.time() < until_ts:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line.decode("utf-8", errors="replace"))
                except Exception:
                    continue
                if handle_broker_message(obj, canal):
                    count += 1
        except socket.timeout:
            pass
        time.sleep(0.02)
    return count

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Probe del broker Meshtastic (v2 con payload→texto y resumen)")
    p.add_argument("--broker", default=os.getenv("MESHTASTIC_BROKER", "127.0.0.1:8765"), help="host:puerto del broker")
    p.add_argument("--dur", type=int, default=30, help="Segundos de escucha")
    p.add_argument("--canal", type=int, default=None, help="Filtrar por canal (None = todos)")
    return p

def main():
    args = build_parser().parse_args()
    print(f"📡 Conectando al broker en {args.broker} …")
    s = open_broker(args.broker)
    print("✅ Conectado.")
    canal_txt = "todos" if args.canal is None else str(args.canal)
    print(f"🎧 Escuchando {args.dur} s (canal: {canal_txt}) …")

    shown = 0
    try:
        shown = read_jsonl_lines(s, time.time() + args.dur, args.canal)
    finally:
        try:
            s.close()
        except Exception:
            pass

    print("⏹ Fin de la escucha.")
    if shown == 0:
        print("ℹ️ No se recibieron paquetes que cumplan el filtro en el intervalo.")

    # Resumen final
    if STATS_PORT or STATS_CH:
        print("\n📊 Resumen:")
        if STATS_PORT:
            print("  Por portnum:", ", ".join(f"{k}:{v}" for k, v in STATS_PORT.items()))
        if STATS_CH:
            print("  Por canal  :", ", ".join(f"{k}:{v}" for k, v in STATS_CH.items()))

if __name__ == "__main__":
    main()
