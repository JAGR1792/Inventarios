from __future__ import annotations

import argparse
import socket
import sys

from inventarios.db import create_engine_from_url, init_db, make_session_factory
from inventarios.settings import Settings
from inventarios.ui.web_server import create_app


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _msgbox(text: str, title: str) -> None:
    # Best-effort: only used for the packaged Windows EXE.
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)  # MB_ICONINFORMATION
    except Exception:
        pass


def _get_lan_ip() -> str:
    # Tries to infer the primary LAN IP by opening a UDP socket.
    # Does not send data.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip:
                return ip
        finally:
            s.close()
    except Exception:
        pass
    return "127.0.0.1"


def _get_hostname() -> str:
    try:
        name = socket.gethostname().strip()
        # Keep it simple/safe for URLs
        name = "".join(ch for ch in name if (ch.isalnum() or ch in "-_"))
        return name
    except Exception:
        return ""


def _ensure_port_free(host: str, port: int) -> bool:
    # Returns True if we can bind (port free), False otherwise.
    # For 0.0.0.0 we bind INADDR_ANY which matches how Flask binds.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
        finally:
            s.close()
    except OSError:
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="Inventarios POS - Web server (LAN/tablet)")
    p.add_argument("--host", default="0.0.0.0", help="Bind host (use 0.0.0.0 for LAN)")
    p.add_argument("--port", type=int, default=8000, help="Port")
    p.add_argument("--debug", action="store_true", help="Flask debug mode")
    p.add_argument(
        "--ui",
        action="store_true",
        help="Show a Windows message box with the LAN URL (enabled automatically in packaged EXE)",
    )
    args = p.parse_args()

    show_ui = bool(args.ui or (_is_frozen() and not args.debug))

    if not _ensure_port_free(args.host, args.port):
        msg = f"El servidor ya está iniciado (o el puerto está ocupado): {args.host}:{args.port}"
        if show_ui:
            _msgbox(msg, "Inventarios - Servidor Tablet")
        else:
            print(msg)
        return 2

    settings = Settings()
    settings.ensure_instance()

    engine = create_engine_from_url(settings.DATABASE_URL)
    init_db(engine)
    session_factory = make_session_factory(engine)

    app = create_app(session_factory, settings)

    # Friendly startup info
    lan_ip = _get_lan_ip() if args.host in ("0.0.0.0", "::") else args.host
    url = f"http://{lan_ip}:{args.port}/"
    health = f"http://{lan_ip}:{args.port}/health"

    host = _get_hostname()
    alt_urls: list[str] = []
    if host:
        alt_urls.append(f"http://{host}:{args.port}/")
        alt_urls.append(f"http://{host}.local:{args.port}/")

    alt = ""
    if alt_urls:
        alt = "\n\nLinks alternativos (si tu red resuelve nombres):\n" + "\n".join(alt_urls)
    msg = (
        "Servidor tablet iniciado.\n\n"
        f"Abre en la tablet:\n{url}\n\n"
        f"(Prueba rápida: {health})\n\n"
        + alt
        + "\n\nSi ya estaba abierto, ignora este mensaje."
    )
    if show_ui:
        _msgbox(msg, "Inventarios - Servidor Tablet")
    else:
        print(msg)

    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
