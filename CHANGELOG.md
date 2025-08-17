# Changelog

## [2.2] - 2025-08-17
### Added
- Integración del bot con broker TCP (`Telegram_Bot_Broker_v2.2.py`).
- Menú inline y comandos oficiales en Telegram.
- Exportación robusta de nodos y traceroute.
- Probe del broker con extracción de payload a texto.

### Fixed
- Compatibilidad Windows/Linux en resolución del CLI.
- División de mensajes largos en Telegram.

### Changed
- Broker ahora siempre incluye `packet.meta.channelIndex`.
- Heartbeat cada 5s + priming periódico para clientes.
