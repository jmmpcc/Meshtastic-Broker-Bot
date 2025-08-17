#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_bot_broker_v2_2.py
---------------------------
Bot de Telegram integrado con Meshtastic y un Broker TCP opcional.
Conexión preferente a Meshtastic_Relay (como en v1), con fallback a CLI Meshtastic.

- SIN AIORateLimiter (no requiere "python-telegram-bot[rate-limiter]").
- Salidas crudas (nodos, traceroute, telemetría, envíos) en HTML <pre> escapado.
- Manejador global de errores + logs en ./bot_data/bot.log (UTF-8).
- Menú inline (v1) + comandos, diálogo guiado para /enviar, broker asíncrono.

Variables de entorno:
  TELEGRAM_TOKEN, ADMIN_IDS, MESHTASTIC_HOST, MESHTASTIC_EXE, BROKER_HOST, BROKER_PORT, BROKER_CHANNEL
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import socket
import sys
import time
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Telegram PTB v20+ ---
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
    ReplyKeyboardRemove,
    ForceReply,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

# -------------------------
# CONFIGURACIÓN Y CONSTANTES
# -------------------------

DATA_DIR           = Path(os.getenv("BOT_DATA_DIR", "./bot_data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE           = DATA_DIR / "bot.log"
STATS_FILE         = DATA_DIR / "stats.json"
NODES_FILE         = DATA_DIR / "nodos.txt"

TOKEN              = os.getenv("TELEGRAM_TOKEN", "7898191886:AAG4XOGcXOJ_Y-L4NdtcY-a84RVA4pEvIwk").strip()
ADMIN_IDS          = {int(x) for x in os.getenv("126867583", "").replace(";", ",").split(",") if x.strip().isdigit()}
MESHTASTIC_HOST    = os.getenv("MESHTASTIC_HOST", "192.168.1.201").strip()
MESHTASTIC_EXE     = os.getenv("MESHTASTIC_EXE", "meshtastic").strip()
BROKER_HOST        = os.getenv("BROKER_HOST", "127.0.0.1").strip()
BROKER_PORT        = int(os.getenv("BROKER_PORT", "8765"))
BROKER_CHANNEL     = int(os.getenv("BROKER_CHANNEL", "0"))

# Tiempos por defecto
TIMEOUT_CMD_S      = int(os.getenv("MESHTASTIC_TIMEOUT", "25"))
TRACEROUTE_TIMEOUT = int(os.getenv("TRACEROUTE_TIMEOUT", "35"))
TELEMETRY_TIMEOUT  = int(os.getenv("TELEMETRY_TIMEOUT", "30"))

# Mensajes largos -> se trocean en Telegram
TELEGRAM_MAX_CHARS = 3900

# Estados de ConversationHandler
ASK_SEND_DEST, ASK_SEND_TEXT = range(2)

# -------------------------
# LOG Y UTILIDADES
# -------------------------

def log(msg: str) -> None:
    """Escribe al log (./bot_data/bot.log) y a consola."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8", errors="ignore") as f:
            f.write(line + "\n")
    except Exception:
        pass


def chunk_text(s: str, limit: int = TELEGRAM_MAX_CHARS) -> List[str]:
    """Divide texto largo en trozos aptos para Telegram."""
    if len(s) <= limit:
        return [s]
    return [s[i:i+limit] for i in range(0, len(s), limit)]


def load_stats() -> Dict[str, Any]:
    """Carga estadísticas simples del bot desde JSON."""
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"users": {}, "counts": {}}


def save_stats(stats: Dict[str, Any]) -> None:
    """Guarda estadísticas en disco."""
    try:
        STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"❗ No se pudo guardar STATS: {e}")


def bump_stat(user_id: int, username: str, command: str) -> None:
    """Incrementa contadores de uso por usuario y por comando."""
    stats = load_stats()
    users = stats.setdefault("users", {})
    counts = stats.setdefault("counts", {})
    u = users.setdefault(str(user_id), {"username": username or "", "last_used": ""})
    u["username"] = username or u.get("username", "")
    u["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
    counts[command] = counts.get(command, 0) + 1
    save_stats(stats)


def is_admin(user_id: int) -> bool:
    """True si el usuario es admin (está en ADMIN_IDS)."""
    return user_id in ADMIN_IDS


# -------------------------
# CAPA DE INTEGRACIÓN CON Meshtastic_Relay (preferente)
# + Fallback a CLI si no existe el módulo o la función
# -------------------------

RELAY = None
def _try_import_relay() -> None:
    """Intenta importar Meshtastic_Relay del mismo directorio."""
    global RELAY
    if RELAY is not None:
        return
    try:
        # Asegura que el cwd esté en sys.path
        if str(Path.cwd()) not in sys.path:
            sys.path.insert(0, str(Path.cwd()))
        import Meshtastic_Relay as relay  # noqa: N813 (estilo de nombre conservado)
        RELAY = relay
        log("🔗 Meshtastic_Relay importado correctamente (modo preferente).")
    except Exception as e:
        RELAY = None
        log(f"ℹ️ Meshtastic_Relay no disponible, usaré CLI. Detalle: {e}")


def _relay_has(*names: str) -> Optional[str]:
    """Devuelve el primer nombre de función disponible en Meshtastic_Relay (o None)."""
    if RELAY is None:
        return None
    for n in names:
        if hasattr(RELAY, n):
            return n
    return None


def run_command(args: List[str], timeout: int = TIMEOUT_CMD_S) -> str:
    """
    Ejecuta la CLI Meshtastic. Se usa como fallback cuando no hay función equivalente en el relay.
    """
    exe = MESHTASTIC_EXE or "meshtastic"
    cmd = [exe] + args
    log(f"💻 Ejecutando: {shlex.join(cmd)}")
    try:
        import subprocess
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        out = (result.stdout or "").strip()
        if not out:
            out = f"(sin salida) rc={result.returncode}"
        return out
    except subprocess.TimeoutExpired:
        return "⏱ Tiempo excedido ejecutando CLI Meshtastic"
    except FileNotFoundError:
        return f"❗ No se encontró el ejecutable '{exe}'. Ajusta MESHTASTIC_EXE o PATH."
    except Exception as e:
        return f"❗ Error ejecutando CLI: {e}"


def sanitize_line(s: str) -> str:
    return s.replace("\x00", "").replace("\r", "")


def write_file_safely(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", errors="ignore")


async def send_pre(message, text: str) -> None:
    await message.reply_text(f"<pre>{escape(text)}</pre>", parse_mode="HTML")


# -------------------------
# API DE NODOS (preferente Relay)
# -------------------------

def sync_nodes_and_save(n_max: int = 20) -> List[str]:
    """
    Obtiene nodos preferentemente desde Meshtastic_Relay; si no, usa CLI '--nodes'.
    Guarda la salida completa en NODES_FILE y devuelve hasta n_max filas legibles.
    """
    _try_import_relay()

    # 1) Relay → intentos de función compatibles
    fn = _relay_has("list_nodes", "get_nodes", "get_visible_nodes", "listar_nodos")
    if fn:
        try:
            rows = getattr(RELAY, fn)(n_max)  # se esperan líneas ya formateadas
            if isinstance(rows, list) and rows:
                write_file_safely(NODES_FILE, "\n".join(rows))
                return rows[:n_max]
        except Exception as e:
            log(f"⚠️ {fn} del relay falló: {e}. Probando CLI…")

    # 2) Fallback CLI
    out = run_command(["--host", MESHTASTIC_HOST, "--nodes"])
    lines = [sanitize_line(x) for x in out.splitlines() if x.strip()]
    if not lines:
        lines = ["(sin líneas de salida)"]

    data_rows: List[str] = []
    for ln in lines:
        if "Connected to radio" in ln or "Aborting due to" in ln:
            continue
        if "╒" in ln or "╘" in ln:
            continue
        if "│" in ln and not ln.strip().startswith("N"):
            data_rows.append(ln.strip())

    selected = data_rows[:n_max] if data_rows else lines[:n_max]
    write_file_safely(NODES_FILE, "\n".join(lines))
    return selected


def get_visible_nodes_from_file_ordenados(n_max: int = 20) -> List[str]:
    if not NODES_FILE.exists():
        log("ℹ️ NODES_FILE no existe; sincronizando automáticamente...")
        return sync_nodes_and_save(n_max=n_max)

    try:
        content = NODES_FILE.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return sync_nodes_and_save(n_max=n_max)

    lines = [sanitize_line(x) for x in content.splitlines() if x.strip()]
    if not any("│" in ln for ln in lines):
        return lines[:n_max]

    data_rows = [ln.strip() for ln in lines if "│" in ln and not ln.strip().startswith("N")]
    return data_rows[:n_max] if data_rows else lines[:n_max]


# -------------------------
# API DE TRACEROUTE / TELEMETRÍA / ENVÍO (preferente Relay)
# -------------------------

@dataclass
class TraceResult:
    ok: bool
    hops: int
    route: List[str] = field(default_factory=list)
    raw: str = ""


def parse_traceroute_output(out: str) -> TraceResult:
    raw = out.strip()
    ok = ("Route traced" in out) or ("-->" in out)
    route: List[str] = []
    hops = 0
    if "-->" in out:
        parts = [p.strip() for p in out.split("-->") if p.strip()]
        route = parts
        hops = max(0, len(parts) - 1)
    elif ok:
        ids = re.findall(r"!?[0-9a-fA-F]{8}", out)
        if ids:
            route = ids
            hops = max(0, len(ids) - 1)
    return TraceResult(ok=ok, hops=hops, route=route, raw=raw)


def traceroute_node(node_id: str, timeout: int = TRACEROUTE_TIMEOUT) -> TraceResult:
    """Usa Relay.traceroute/do_traceroute/... o CLI '--traceroute'."""
    _try_import_relay()

    fn = _relay_has("traceroute", "do_traceroute", "trace_route", "traza_ruta")
    if fn:
        try:
            # Acepta distintos retornos: dict/obj con keys 'ok','hops','route','raw' o tupla
            res = getattr(RELAY, fn)(node_id, timeout=timeout)  # type: ignore
            if isinstance(res, dict):
                return TraceResult(
                    ok=bool(res.get("ok", False)),
                    hops=int(res.get("hops", 0)),
                    route=list(res.get("route", [])),
                    raw=str(res.get("raw", "")),
                )
            if isinstance(res, (list, tuple)) and res:
                # posibles formatos: (ok, hops, route, raw) o (hops, route) …
                if len(res) == 4 and isinstance(res[2], (list, tuple)):
                    return TraceResult(bool(res[0]), int(res[1]), list(res[2]), str(res[3]))
                if len(res) == 3 and isinstance(res[2], (list, tuple)):
                    return TraceResult(True, int(res[1]), list(res[2]), "")
        except Exception as e:
            log(f"⚠️ {fn} del relay falló: {e}. Probando CLI…")

    # Fallback CLI
    out = run_command(["--host", MESHTASTIC_HOST, "--traceroute", node_id], timeout=timeout)
    return parse_traceroute_output(out)


def request_telemetry(node_id: str, timeout: int = TELEMETRY_TIMEOUT) -> str:
    """Usa Relay.request_telemetry/... o varias banderas de CLI como fallback."""
    _try_import_relay()

    fn = _relay_has("request_telemetry", "telemetry", "getTelemetry", "solicitar_telemetria")
    if fn:
        try:
            out = getattr(RELAY, fn)(node_id, timeout=timeout)  # type: ignore
            if isinstance(out, (list, tuple)):
                out = "\n".join(str(x) for x in out)
            return str(out)
        except Exception as e:
            log(f"⚠️ {fn} del relay falló: {e}. Probando CLI…")

    # Fallback CLI
    flags_try = [
        ["--request-telemetry", node_id],
        ["--requestPosition", node_id],
        ["--get", "telemetry", "--dest", node_id],
    ]
    for flags in flags_try:
        out = run_command(["--host", MESHTASTIC_HOST] + flags, timeout=timeout)
        if "Unknown option" in out or "invalid" in out:
            continue
        if out.strip():
            return out
    return "No se pudo solicitar telemetría con las banderas conocidas."


def send_text_message(node_id: Optional[str], text: str, canal: int = 0) -> str:
    """Usa Relay.send_text/... o CLI '--sendtext' como fallback."""
    _try_import_relay()

    fn = _relay_has("send_text", "sendText", "send_message", "enviar_texto")
    if fn:
        try:
            out = getattr(RELAY, fn)(node_id, text, canal)  # type: ignore
            if isinstance(out, (list, tuple)):
                out = "\n".join(str(x) for x in out)
            return str(out or "Envío realizado (relay)")
        except Exception as e:
            log(f"⚠️ {fn} del relay falló: {e}. Probando CLI…")

    # Fallback CLI
    args = ["--host", MESHTASTIC_HOST, "--sendtext", text, "--ch-index", str(canal)]
    if node_id:
        args += ["--dest", node_id]
    out = run_command(args, timeout=TIMEOUT_CMD_S)
    return out or "Envío realizado (CLI, sin salida)"


# -------------------------
# INTERFAZ BROKER TCP (opcional)
# -------------------------

class BrokerClient:
    """Cliente asíncrono para un broker TCP de mensajes Meshtastic."""
    def __init__(self, host: str, port: int, channel: int, on_message_coro):
        self.host = host
        self.port = port
        self.channel = channel
        self.on_message_coro = on_message_coro  # async def(chat_id, text)
        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()
        self._running.clear()
        self._chat_ids: set[int] = set()

    def add_chat(self, chat_id: int) -> None:
        self._chat_ids.add(chat_id)

    def remove_chat(self, chat_id: int) -> None:
        self._chat_ids.discard(chat_id)

    def chats(self) -> List[int]:
        return sorted(self._chat_ids)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running.set()
        self._task = asyncio.create_task(self._run_loop(), name="broker-client-loop")

    async def stop(self) -> None:
        self._running.clear()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        backoff = 1.5
        delay = 1.0
        while self._running.is_set():
            try:
                log(f"🔌 Conectando a broker {self.host}:{self.port}…")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                log("✅ Conectado al broker.")
                try:
                    writer.write(f"SUB {self.channel}\n".encode("utf-8", errors="ignore"))
                    await writer.drain()
                except Exception:
                    pass
                delay = 1.0
                while self._running.is_set():
                    line = await reader.readline()
                    if not line:
                        raise ConnectionError("Conexión cerrada por el broker.")
                    text = line.decode("utf-8", errors="ignore").strip()
                    if not text:
                        continue
                    for chat_id in list(self._chat_ids):
                        try:
                            await self.on_message_coro(chat_id, f"🔔 Broker: {text}")
                        except Exception as e:
                            log(f"❗ Error enviando mensaje del broker a chat {chat_id}: {e}")
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                log(f"⚠️ Broker desconectado: {e}. Reintentando en {delay:.1f}s…")
                await asyncio.sleep(delay)
                delay = min(delay * backoff, 60.0)


# -------------------------
# TELEGRAM: MENÚS Y COMANDOS
# -------------------------

def main_menu_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📡 Ver últimos nodos", callback_data="ver_nodos")],
        [InlineKeyboardButton("🧭 Traceroute", callback_data="traceroute"),
         InlineKeyboardButton("🛰️ Telemetría", callback_data="telemetria")],
        [InlineKeyboardButton("✉️ Enviar mensaje", callback_data="enviar")],
        [InlineKeyboardButton("👂 Escuchar broker", callback_data="escuchar"),
         InlineKeyboardButton("⏹️ Parar escucha", callback_data="parar_escucha")],
        [InlineKeyboardButton("👥 Vecinos directos", callback_data="vecinos")],
        [InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda")],
    ]
    return InlineKeyboardMarkup(buttons)


async def set_bot_menu(app: Application) -> None:
    default_cmds = [
        BotCommand("start", "Mostrar menú principal"),
        BotCommand("menu", "Abrir menú principal"),
        BotCommand("ver_nodos", "Ver últimos nodos o sincronizar"),
        BotCommand("traceroute", "Traceroute a un nodo (!id)"),
        BotCommand("telemetria", "Solicitar telemetría a un nodo (!id)"),
        BotCommand("enviar", "Enviar mensaje a nodo o broadcast"),
        BotCommand("escuchar", "Empezar a escuchar el broker"),
        BotCommand("parar_escucha", "Detener la escucha del broker"),
        BotCommand("vecinos", "Listar vecinos directos"),
        BotCommand("estado", "Comprobar estado host/broker"),
        BotCommand("ayuda", "Ayuda general"),
    ]
    await app.bot.set_my_commands(default_cmds, scope=BotCommandScopeDefault())
    admin_cmds = default_cmds + [BotCommand("estadistica", "Uso del bot (solo admin)")]
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            log(f"❗ set_my_commands admin {admin_id}: {e}")


# ---- Básicos

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "start")
    await set_bot_menu(context.application)
    text = (
        "🤖 Meshtastic Bot listo.\n"
        f"- Nodo: {MESHTASTIC_HOST}\n"
        f"- Broker: {BROKER_HOST}:{BROKER_PORT} canal {BROKER_CHANNEL}\n\n"
        "Elige una opción:"
    )
    await update.effective_message.reply_text(text, reply_markup=main_menu_kb())


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "menu")
    await update.effective_message.reply_text("Menú principal:", reply_markup=main_menu_kb())


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "ayuda")
    text = (
        "Ayuda rápida\n"
        "/ver_nodos [N] – últimos N nodos (predet. 20)\n"
        "/traceroute !id – ruta completa hacia el nodo\n"
        "/telemetria !id – solicita telemetría\n"
        "/enviar [!id|broadcast] texto… – envía un mensaje\n"
        "/escuchar – escuchar broker\n"
        "/parar_escucha – detener broker\n"
        "/vecinos – vecinos directos (1 salto)\n"
        "/estado – comprobar estado\n"
        "/estadistica – (admin) uso del bot\n"
    )
    await update.effective_message.reply_text(text)


# ---- Nodos / Vecinos

async def ver_nodos_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "ver_nodos")
    try:
        n = int(context.args[0]) if context.args else 20
    except ValueError:
        n = 20
    rows = get_visible_nodes_from_file_ordenados(n_max=n)
    if not rows:
        rows = sync_nodes_and_save(n_max=n)
    text = "📡 Últimos nodos visibles\n" + "\n".join(rows)
    for chunk in chunk_text(text):
        await send_pre(update.effective_message, chunk)


def _ids_from_rows(rows: List[str]) -> List[str]:
    ids: List[str] = []
    for ln in rows:
        ids += re.findall(r"!?[0-9a-fA-F]{8}", ln)
    # únicos manteniendo orden
    seen = set()
    uniq = []
    for nid in ids:
        if nid not in seen:
            uniq.append(nid)
            seen.add(nid)
    return uniq


async def vecinos_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "vecinos")
    rows = get_visible_nodes_from_file_ordenados(n_max=50)
    ids = _ids_from_rows(rows)
    if not ids:
        await update.effective_message.reply_text("No se pudieron extraer IDs. Prueba /ver_nodos primero.")
        return
    await update.effective_message.reply_text(f"Analizando {len(ids)} nodos; esto puede tardar…")
    one_hop: List[str] = []
    for nid in ids:
        res = traceroute_node(nid)
        if res.ok and res.hops == 1:
            one_hop.append(f"{nid}  (ruta: {' --> '.join(res.route) if res.route else '1 salto'})")
    text = "👥 Vecinos directos (1 salto)\n" + ("\n".join(one_hop) if one_hop else "Ninguno encontrado.")
    await update.effective_message.reply_text(text)


# ---- Traceroute

async def traceroute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "traceroute")
    if not context.args:
        await update.effective_message.reply_text("Uso: /traceroute !id (ej. /traceroute !cdada0c1)")
        return
    node_id = context.args[0].strip()
    res = traceroute_node(node_id)
    if res.ok:
        ruta = " --> ".join(res.route) if res.route else "(ruta no desglosada)"
        text = f"🧭 Traceroute a {node_id}\nSaltos: {res.hops}\nRuta: {ruta}"
    else:
        text = f"No se encontró ruta hacia {node_id}.\n\nSalida:\n{res.raw}"
    for chunk in chunk_text(text):
        await send_pre(update.effective_message, chunk)


# ---- Telemetría

async def telemetria_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "telemetria")
    if not context.args:
        await update.effective_message.reply_text("Uso: /telemetria !id (ej. /telemetria !cdada0c1)")
        return
    node_id = context.args[0].strip()
    out = request_telemetry(node_id)
    text = f"🛰️ Telemetría solicitada a {node_id}\n{out}"
    for chunk in chunk_text(text):
        await send_pre(update.effective_message, chunk)


# ---- Enviar

async def enviar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "enviar")
    args = context.args or []
    if len(args) >= 2:
        dest = args[0].strip()
        text = " ".join(args[1:]).strip()
        node = None if dest.lower() == "broadcast" else dest
        out = send_text_message(node, text, canal=BROKER_CHANNEL)
        await send_pre(update.effective_message, f"✉️ Envío: {dest}\n{out}")
        return ConversationHandler.END
    await update.effective_message.reply_text(
        "¿A quién quieres enviar?\nIndica !id o escribe broadcast.",
        reply_markup=ForceReply(selective=True),
    )
    return ASK_SEND_DEST


async def on_send_dest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dest = update.effective_message.text.strip()
    context.user_data["send_dest"] = dest
    await update.effective_message.reply_text("Escribe el texto a enviar:", reply_markup=ForceReply(selective=True))
    return ASK_SEND_TEXT


async def on_send_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    dest = context.user_data.get("send_dest", "broadcast")
    node = None if dest.lower() == "broadcast" else dest
    out = send_text_message(node, text, canal=BROKER_CHANNEL)
    await send_pre(update.effective_message, f"✉️ Envío: {dest}\n{out}")
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ---- Broker

BROKER: Optional[BrokerClient] = None

async def escuchar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global BROKER
    bump_stat(update.effective_user.id, update.effective_user.username or "", "escuchar")
    if not BROKER_HOST:
        await update.effective_message.reply_text("No hay BROKER_HOST configurado. Define BROKER_HOST/BROKER_PORT.")
        return
    if BROKER is None:
        async def _forward_broker(chat_id: int, text: str):
            await context.bot.send_message(chat_id=chat_id, text=text)
        BROKER = BrokerClient(BROKER_HOST, BROKER_PORT, BROKER_CHANNEL, _forward_broker)
    BROKER.add_chat(update.effective_chat.id)
    await BROKER.start()
    await update.effective_message.reply_text(
        f"👂 Escuchando broker {BROKER_HOST}:{BROKER_PORT} canal {BROKER_CHANNEL} para este chat."
    )


async def parar_escucha_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global BROKER
    bump_stat(update.effective_user.id, update.effective_user.username or "", "parar_escucha")
    if not BROKER:
        await update.effective_message.reply_text("El broker no está activo.")
        return
    BROKER.remove_chat(update.effective_chat.id)
    if not BROKER.chats():
        await BROKER.stop()
        await update.effective_message.reply_text("⏹️ Escucha del broker detenida.")
    else:
        await update.effective_message.reply_text("Este chat dejó de escuchar; otros siguen suscritos.")


# ---- Estado / Estadística

async def estado_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bump_stat(update.effective_user.id, update.effective_user.username or "", "estado")

    def tcp_check(host: str, port: int, timeout: float = 2.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    broker_ok = tcp_check(BROKER_HOST, BROKER_PORT, 2.0) if BROKER_HOST else False

    # Intento ligero de info por relay
    _try_import_relay()
    host_ok = False
    if _relay_has("info", "get_info", "estado_host"):
        try:
            info_out = getattr(RELAY, _relay_has("info", "get_info", "estado_host"))()  # type: ignore
            host_ok = bool(info_out)
        except Exception:
            host_ok = False
    else:
        out = run_command(["--host", MESHTASTIC_HOST, "--info"], timeout=10)
        host_ok = "Connected to radio" in out or bool(out.strip())

    text = (
        "Estado:\n"
        f"- Meshtastic host {MESHTASTIC_HOST}: {'OK' if host_ok else 'KO'}\n"
        f"- Broker {BROKER_HOST}:{BROKER_PORT}: {'OK' if broker_ok else 'KO'}\n"
    )
    await update.effective_message.reply_text(text)


async def estadistica_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        await update.effective_message.reply_text("Solo disponible para admins.")
        return
    bump_stat(user.id, user.username or "", "estadistica")
    stats = load_stats()
    users = stats.get("users", {})
    counts = stats.get("counts", {})
    parts = ["Estadísticas de uso"]
    if users:
        parts.append("\nUsuarios:")
        for uid, info in users.items():
            uname = info.get("username") or "(sin username)"
            last = info.get("last_used")
            parts.append(f"- {uname} (id {uid}) • última vez: {last}")
    if counts:
        parts.append("\nComandos:")
        for cmd, num in counts.items():
            parts.append(f"- /{cmd}: {num}")
    await update.effective_message.reply_text("\n".join(parts))


# ---- Callbacks de menú

async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "ver_nodos":
        rows = get_visible_nodes_from_file_ordenados(n_max=20)
        if not rows:
            rows = sync_nodes_and_save(n_max=20)
        text = "📡 Últimos nodos visibles\n" + "\n".join(rows)
        for chunk in chunk_text(text):
            await send_pre(query.message, chunk)

    elif data == "traceroute":
        await query.message.reply_text("Introduce !id del nodo para traceroute (ej.: !cdada0c1).",
                                       reply_markup=ForceReply())
        context.user_data["await_traceroute"] = True

    elif data == "telemetria":
        await query.message.reply_text("Introduce !id del nodo para solicitar telemetría.",
                                       reply_markup=ForceReply())
        context.user_data["await_telemetry"] = True

    elif data == "enviar":
        await query.message.reply_text("Destino !id o broadcast:", reply_markup=ForceReply())
        context.user_data["await_send_dest"] = True

    elif data == "escuchar":
        await escuchar_cmd(update, context)

    elif data == "parar_escucha":
        await parar_escucha_cmd(update, context)

    elif data == "vecinos":
        await vecinos_cmd(update, context)

    elif data == "ayuda":
        await ayuda(update, context)


async def on_forcereply_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.effective_message.text or "").strip()
    if context.user_data.pop("await_traceroute", False):
        res = traceroute_node(text)
        if res.ok:
            ruta = " --> ".join(res.route) if res.route else "(ruta no desglosada)"
            out = f"🧭 Traceroute a {text}\nSaltos: {res.hops}\nRuta: {ruta}"
        else:
            out = f"No se encontró ruta hacia {text}.\n\nSalida:\n{res.raw}"
        for chunk in chunk_text(out):
            await send_pre(update.effective_message, chunk)
        return

    if context.user_data.pop("await_telemetry", False):
        out = request_telemetry(text)
        txt = f"🛰️ Telemetría solicitada a {text}\n{out}"
        for chunk in chunk_text(txt):
            await send_pre(update.effective_message, chunk)
        return

    if context.user_data.get("await_send_dest"):
        context.user_data["send_dest_menu"] = text
        context.user_data.pop("await_send_dest", None)
        await update.effective_message.reply_text("Ahora, escribe el texto a enviar:", reply_markup=ForceReply())
        context.user_data["await_send_text"] = True
        return

    if context.user_data.pop("await_send_text", False):
        dest = context.user_data.pop("send_dest_menu", "broadcast")
        node = None if dest.lower() == "broadcast" else dest
        out = send_text_message(node, text, canal=BROKER_CHANNEL)
        ans = f"✉️ Envío: {dest}\n{out}"
        for chunk in chunk_text(ans):
            await send_pre(update.effective_message, chunk)
        return


# -------------------------
# ENSAMBLADO DEL BOT
# -------------------------

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        log(f"❌ Excepción no capturada: {context.error}")
    except Exception:
        pass


def build_application() -> Application:
    if not TOKEN:
        print("❗ Falta TELEGRAM_TOKEN en variables de entorno.", file=sys.stderr)
        sys.exit(2)

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_error_handler(on_error)

    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("ver_nodos", ver_nodos_cmd))
    app.add_handler(CommandHandler("vecinos", vecinos_cmd))
    app.add_handler(CommandHandler("traceroute", traceroute_cmd))
    app.add_handler(CommandHandler("telemetria", telemetria_cmd))
    app.add_handler(CommandHandler("escuchar", escuchar_cmd))
    app.add_handler(CommandHandler("parar_escucha", parar_escucha_cmd))
    app.add_handler(CommandHandler("estado", estado_cmd))
    app.add_handler(CommandHandler("estadistica", estadistica_cmd))

    # Diálogo /enviar
    conv = ConversationHandler(
        entry_points=[CommandHandler("enviar", enviar_cmd)],
        states={
            ASK_SEND_DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_send_dest)],
            ASK_SEND_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_send_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name="enviar_conv",
        persistent=False,
    )
    app.add_handler(conv)

    # Menú (callback) y ForceReply del menú
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.REPLY & ~filters.COMMAND, on_forcereply_text))

    return app


async def post_startup(app: Application) -> None:
    await set_bot_menu(app)
    log("🤖 Bot arrancado y listo. Menú establecido.")


def main() -> None:
    app = build_application()
    app.post_init = post_startup
    log("Iniciando bot…")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        close_loop=False,
        stop_signals=None,
    )


if __name__ == "__main__":
    main()


# -----------------------------------------------------------------------------
# RESUMEN DE FUNCIONES (qué hace cada una)
# -----------------------------------------------------------------------------
# _try_import_relay()          -> Importa Meshtastic_Relay si está disponible (misma carpeta).
# _relay_has(*nombres)         -> Comprueba si el relay expone una función (p.ej. 'traceroute').
# run_command(args, timeout)   -> Ejecuta CLI Meshtastic; usado solo como fallback.
# sync_nodes_and_save(n)       -> Obtiene nodos por relay (list_nodes/get_nodes…) o CLI; guarda nodos.txt.
# get_visible_nodes_from_file_ordenados(n)
#                             -> Lee nodos.txt y devuelve líneas "bonitas" (o sincroniza si falta).
# traceroute_node(id, t)       -> Usa relay.traceroute/do_traceroute/... o CLI; devuelve TraceResult.
# request_telemetry(id, t)     -> Usa relay.request_telemetry/... o prueba varias banderas CLI.
# send_text_message(id, txt, ch)
#                             -> Usa relay.send_text/send_message/... o CLI '--sendtext'.
# BrokerClient                 -> Cliente TCP asíncrono con reconexión y lista de chats suscritos.
# Handlers Telegram            -> start/menu/ayuda/ver_nodos/vecinos/traceroute/telemetria/enviar/escuchar/...
# on_cb / on_forcereply_text   -> Menú inline (v1) y flujos con ForceReply.
# on_error                     -> Loguea excepciones PTB.
# build_application()          -> Ensambla la app PTB con todos los handlers.
# -----------------------------------------------------------------------------
