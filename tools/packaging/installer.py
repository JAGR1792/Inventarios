from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import textwrap
import venv
from pathlib import Path


# NOTE:
# - When this script is packaged with PyInstaller, it acts as a *real installer*:
#   it copies the bundled app EXE to a user-writable install folder and creates shortcuts.
# - When executed as plain Python (repo checkout), it can bootstrap everything:
#   create venv, install deps, build the app EXE, build the installer EXE, and install.


APP_DISPLAY_NAME = "Inventarios POS"
INSTALL_DIR_NAME = "Inventarios_POS"
ICON_FILE_NAME = "app.ico"

SERVER_DISPLAY_NAME = "Inventarios POS - Servidor Tablet"
SERVER_EXE_CANONICAL_NAME = "InventariosServer.exe"

# Current build name is InventariosPOS.exe (per README/scripts). Keep legacy names for compatibility.
APP_EXE_CANONICAL_NAME = "InventariosPOS.exe"
APP_EXE_CANDIDATES = [
    APP_EXE_CANONICAL_NAME,
    "Inventarios POS.exe",
    "Inventario GAROM.exe",
]

# Defaults for build outputs
APP_BUILD_NAME = "InventariosPOS"
INSTALLER_BUILD_NAME = "InstalarInventarios"
SERVER_BUILD_NAME = "InventariosServer"

SERVER_EXE_CANDIDATES = [
    SERVER_EXE_CANONICAL_NAME,
    "Inventarios Server.exe",
]


def _msgbox(text: str, title: str, flags: int = 0) -> int:
    # flags: https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-messageboxw
    try:
        import ctypes

        return int(ctypes.windll.user32.MessageBoxW(0, text, title, flags))
    except Exception:
        # Fallback to console if something is very wrong
        try:
            print(f"[{title}] {text}")
        except Exception:
            pass
        return 0


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _bundle_root() -> Path:
    if _is_frozen() and getattr(sys, "_MEIPASS", None):
        return Path(str(sys._MEIPASS))  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _default_install_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return (Path(base) / INSTALL_DIR_NAME).resolve()


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _venv_python(venv_dir: Path) -> Path:
    # Windows layout; this project targets Windows for EXE/installer.
    return (venv_dir / "Scripts" / "python.exe").resolve()


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if p.returncode != 0:
        raise RuntimeError(f"Falló comando (exit={p.returncode}): {' '.join(cmd)}")


def _find_source_app_exe() -> Path:
    # When running as installer.exe, we bundle the app exe as data next to _MEIPASS.
    root = _bundle_root()

    candidates: list[Path] = []
    for exe_name in APP_EXE_CANDIDATES:
        candidates += [
            root / exe_name,
            root / "dist" / exe_name,
            root / "dist" / APP_BUILD_NAME / exe_name,
        ]

    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(
        "No se encontró el EXE de la app. Esperado alguno de: "
        + ", ".join(APP_EXE_CANDIDATES)
        + "\n\nTip: primero construye el EXE (PyInstaller) antes del instalador."
    )


def _find_source_server_exe() -> Path | None:
    # Optional: older installers may not bundle the server EXE.
    root = _bundle_root()

    candidates: list[Path] = []
    for exe_name in SERVER_EXE_CANDIDATES:
        candidates += [
            root / exe_name,
            root / "dist" / exe_name,
            root / "dist" / SERVER_BUILD_NAME / exe_name,
        ]

    for c in candidates:
        if c.exists():
            return c
    return None


def _find_source_icon() -> Path | None:
    root = _bundle_root()
    candidates = [
        root / ICON_FILE_NAME,
        root / "assets" / ICON_FILE_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None



def _get_folder_path_csidl(csidl: int) -> Path | None:
    # Use SHGetFolderPathW (works on Windows 7+ and respects localized/redirected folders).
    try:
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        # HRESULT SHGetFolderPathW(HWND, int, HANDLE, DWORD, LPWSTR)
        hr = ctypes.windll.shell32.SHGetFolderPathW(0, csidl, 0, 0, buf)
        if int(hr) != 0:
            return None
        p = Path(buf.value).resolve()
        if str(p):
            return p
        return None
    except Exception:
        return None


def _create_shortcut_windows(shortcut_path: Path, target_path: Path, working_dir: Path, icon_path: Path | None) -> None:
    # Prefer PowerShell COM because it's available on normal Windows machines.
    # IconLocation format: "C:\\path\\file.ico,0" or "C:\\path\\app.exe,0"
    icon_loc = ""
    if icon_path and icon_path.exists():
        icon_loc = str(icon_path) + ",0"
    else:
        # Fallback to the icon embedded in the target exe.
        icon_loc = str(target_path) + ",0"

    ps_command = (
        "& { "
        "param($lnk,$target,$wd,$icon,$desc) "
        "$WshShell = New-Object -ComObject WScript.Shell; "
        "$Shortcut = $WshShell.CreateShortcut($lnk); "
        "$Shortcut.TargetPath = $target; "
        "$Shortcut.WorkingDirectory = $wd; "
        "if ($icon) { $Shortcut.IconLocation = $icon }; "
        "if ($desc) { $Shortcut.Description = $desc }; "
        "$Shortcut.Save(); "
        "}"
    )

    ps = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps_command,
        "-Args",
        str(shortcut_path),
        str(target_path),
        str(working_dir),
        icon_loc,
        APP_DISPLAY_NAME,
    ]

    subprocess.run(ps, check=True, capture_output=True)


def _desktop_shortcut_path() -> Path:
    # CSIDL_DESKTOPDIRECTORY = 0x10
    desktop = _get_folder_path_csidl(0x10)
    if desktop:
        return (desktop / f"{APP_DISPLAY_NAME}.lnk").resolve()
    return Path(os.path.join(os.path.expanduser("~"), "Desktop", f"{APP_DISPLAY_NAME}.lnk")).resolve()


def _startmenu_shortcut_path() -> Path:
    # Per-user Start Menu Programs (CSIDL_PROGRAMS = 0x2)
    programs = _get_folder_path_csidl(0x2)
    if programs:
        return (programs / f"{APP_DISPLAY_NAME}.lnk").resolve()
    base = os.environ.get("APPDATA")
    if not base:
        return Path("")
    return (Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{APP_DISPLAY_NAME}.lnk").resolve()


def _startup_shortcut_path(name: str) -> Path:
    # Per-user Startup folder (CSIDL_STARTUP = 0x7)
    startup = _get_folder_path_csidl(0x7)
    if startup:
        return (startup / f"{name}.lnk").resolve()
    base = os.environ.get("APPDATA")
    if not base:
        return Path("")
    return (
        Path(base)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / f"{name}.lnk"
    ).resolve()


def _install_from_exe(
    source_exe: Path,
    install_dir: Path,
    *,
    launch: bool | None = None,
    server_source_exe: Path | None = None,
) -> None:
    _ensure_dir(install_dir)

    dst_exe = (install_dir / APP_EXE_CANONICAL_NAME).resolve()
    shutil.copy2(source_exe, dst_exe)

    # Optional tablet server exe
    server_src = server_source_exe or _find_source_server_exe()
    server_dst = None
    if server_src and server_src.exists():
        server_dst = (install_dir / SERVER_EXE_CANONICAL_NAME).resolve()
        try:
            shutil.copy2(server_src, server_dst)
        except Exception:
            server_dst = None

    src_icon = _find_source_icon()
    dst_icon = None
    if src_icon:
        dst_icon = (install_dir / ICON_FILE_NAME).resolve()
        try:
            shutil.copy2(src_icon, dst_icon)
        except Exception:
            dst_icon = None

    # Shortcuts
    shortcut_errors: list[str] = []
    desktop = _desktop_shortcut_path()
    start = _startmenu_shortcut_path()

    try:
        _create_shortcut_windows(desktop, dst_exe, install_dir, dst_icon)
    except Exception:
        shortcut_errors.append("Escritorio")

    try:
        if str(start):
            _ensure_dir(start.parent)
            _create_shortcut_windows(start, dst_exe, install_dir, dst_icon)
    except Exception:
        shortcut_errors.append("Menú Inicio")

    # Tablet server shortcuts (if bundled)
    if server_dst and server_dst.exists():
        try:
            desktop_server = desktop.parent / f"{SERVER_DISPLAY_NAME}.lnk"
            _create_shortcut_windows(desktop_server, server_dst, install_dir, dst_icon)
        except Exception:
            shortcut_errors.append("Escritorio (Servidor Tablet)")

        try:
            if str(start):
                start_server = start.parent / f"{SERVER_DISPLAY_NAME}.lnk"
                _ensure_dir(start_server.parent)
                _create_shortcut_windows(start_server, server_dst, install_dir, dst_icon)
        except Exception:
            shortcut_errors.append("Menú Inicio (Servidor Tablet)")

        # Offer auto-start on login (Startup folder)
        try:
            res = _msgbox(
                "¿Quieres que el Servidor Tablet se inicie automáticamente al prender Windows?\n\n"
                "Recomendado si usas tablets por WiFi/LAN.",
                SERVER_DISPLAY_NAME,
                0x40 | 0x4,  # MB_ICONINFORMATION | MB_YESNO
            )
            if res == 6:  # IDYES
                startup = _startup_shortcut_path(SERVER_DISPLAY_NAME)
                if str(startup):
                    _ensure_dir(startup.parent)
                    _create_shortcut_windows(startup, server_dst, install_dir, dst_icon)
        except Exception:
            # Non-fatal
            pass

    if shortcut_errors:
        _msgbox(
            "Instalación completada, pero no se pudo crear acceso directo en: "
            + ", ".join(shortcut_errors)
            + "\n\nLa app igual quedó instalada y puedes abrirla desde:\n"
            + str(dst_exe),
            APP_DISPLAY_NAME,
            0x30,  # MB_ICONWARNING
        )

    if launch is None:
        # Ask to launch
        res = _msgbox(
            f"Instalación completa.\n\nSe instaló en:\n{install_dir}\n\n¿Abrir {APP_DISPLAY_NAME} ahora?",
            APP_DISPLAY_NAME,
            0x40 | 0x4,  # MB_ICONINFORMATION | MB_YESNO
        )
        launch = res == 6  # IDYES

    if launch:
        try:
            subprocess.Popen([str(dst_exe)], cwd=str(install_dir))
        except Exception:
            pass


def _ensure_venv(venv_dir: Path) -> Path:
    if not venv_dir.exists():
        builder = venv.EnvBuilder(with_pip=True, clear=False, symlinks=False, upgrade=False)
        builder.create(str(venv_dir))
    py = _venv_python(venv_dir)
    if not py.exists():
        raise FileNotFoundError(f"No se encontró python del venv en: {py}")
    return py


def _pip_install(py: Path, requirements: Path) -> None:
    if not requirements.exists():
        raise FileNotFoundError(f"No existe {requirements}")
    _run([str(py), "-m", "pip", "install", "-r", str(requirements)])


def _clean_build_artifacts(repo_root: Path) -> None:
    for name in ("build", "dist", "dist_installer"):
        p = (repo_root / name).resolve()
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)


def _build_app_exe(py: Path, repo_root: Path, *, onefile: bool) -> Path:
    icon = (repo_root / "assets" / ICON_FILE_NAME).resolve()
    has_icon = icon.exists()

    add_data_web = "inventarios\\ui\\web;inventarios\\ui\\web"
    add_data_assets = "assets;assets"
    mode_args = ["--onefile"] if onefile else ["--onedir"]

    cmd = [
        str(py),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_BUILD_NAME,
        "--add-data",
        add_data_web,
        "--add-data",
        add_data_assets,
        "--collect-all",
        "webview",
    ] + mode_args

    if has_icon:
        cmd += ["--icon", str(icon)]

    cmd += ["run_desktop.py"]
    _run(cmd, cwd=repo_root)

    if onefile:
        exe = (repo_root / "dist" / f"{APP_BUILD_NAME}.exe").resolve()
        if exe.exists():
            return exe
        # fallback if name differs
        for candidate in (repo_root / "dist").glob("*.exe"):
            if candidate.name.lower().startswith(APP_BUILD_NAME.lower()):
                return candidate.resolve()
        raise FileNotFoundError("PyInstaller terminó pero no encontré el EXE en dist/")

    # onedir
    exe = (repo_root / "dist" / APP_BUILD_NAME / f"{APP_BUILD_NAME}.exe").resolve()
    if exe.exists():
        return exe
    raise FileNotFoundError("PyInstaller terminó pero no encontré el EXE en dist/<name>/")


def _build_server_exe(py: Path, repo_root: Path, *, onefile: bool) -> Path:
    icon = (repo_root / "assets" / ICON_FILE_NAME).resolve()
    has_icon = icon.exists()

    add_data_web = "inventarios\\ui\\web;inventarios\\ui\\web"
    add_data_assets = "assets;assets"
    mode_args = ["--onefile"] if onefile else ["--onedir"]

    cmd = [
        str(py),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        SERVER_BUILD_NAME,
        "--add-data",
        add_data_web,
        "--add-data",
        add_data_assets,
    ] + mode_args

    if has_icon:
        cmd += ["--icon", str(icon)]

    cmd += ["run_server.py"]
    _run(cmd, cwd=repo_root)

    if onefile:
        exe = (repo_root / "dist" / f"{SERVER_BUILD_NAME}.exe").resolve()
        if exe.exists():
            return exe
        for candidate in (repo_root / "dist").glob("*.exe"):
            if candidate.name.lower().startswith(SERVER_BUILD_NAME.lower()):
                return candidate.resolve()
        raise FileNotFoundError("PyInstaller (server) terminó pero no encontré el EXE en dist/")

    exe = (repo_root / "dist" / SERVER_BUILD_NAME / f"{SERVER_BUILD_NAME}.exe").resolve()
    if exe.exists():
        return exe
    raise FileNotFoundError("PyInstaller (server) terminó pero no encontré el EXE en dist/<name>/")


def _build_installer_exe(py: Path, repo_root: Path, app_exe: Path, server_exe: Path | None = None) -> Path:
    if not app_exe.exists():
        raise FileNotFoundError(f"No se encontró AppExe: {app_exe}")

    icon = (repo_root / "assets" / ICON_FILE_NAME).resolve()
    has_icon = icon.exists()

    add_data_app = f"{app_exe};."
    cmd = [
        str(py),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        INSTALLER_BUILD_NAME,
        "--distpath",
        "dist_installer",
        "--onefile",
        "--add-data",
        add_data_app,
    ]

    if server_exe and server_exe.exists():
        cmd += ["--add-data", f"{server_exe};."]

    # Bundle icon if present (both as installer icon and as data for shortcut icon)
    if has_icon:
        cmd += ["--add-data", f"assets\\{ICON_FILE_NAME};.", "--icon", str(icon)]

    cmd += ["installer.py"]
    _run(cmd, cwd=repo_root)

    out = (repo_root / "dist_installer" / f"{INSTALLER_BUILD_NAME}.exe").resolve()
    if not out.exists():
        raise FileNotFoundError("PyInstaller (installer) terminó pero no encontré el EXE en dist_installer/")
    return out


def _prepare_runtime(py: Path, repo_root: Path) -> None:
    # Create instance folder + initialize SQLite schema without launching UI.
    code = (
        "from inventarios.settings import Settings;"
        "from inventarios.db import create_engine_from_url, init_db;"
        "s=Settings(); s.ensure_instance();"
        "e=create_engine_from_url(s.DATABASE_URL); init_db(e);"
        "print('OK')"
    )
    _run([str(py), "-c", code], cwd=repo_root)


def _bootstrap_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="installer.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            f"""\
            Bootstrap + Build + Install (Windows)

            Uso típico (un solo comando):
              python installer.py

            Esto crea .venv, instala deps, construye dist/{APP_BUILD_NAME}.exe,
            construye dist_installer/{INSTALLER_BUILD_NAME}.exe e instala la app
            en %LOCALAPPDATA%/{INSTALL_DIR_NAME} con accesos directos.
            """
        ),
    )

    parser.add_argument("--no-venv", action="store_true", help="No crear/usar .venv (usa python actual).")
    parser.add_argument("--no-deps", action="store_true", help="No instalar requirements.")
    parser.add_argument("--no-build", action="store_true", help="No construir EXE/installer.")
    parser.add_argument("--no-install", action="store_true", help="No copiar al directorio de instalación.")
    parser.add_argument("--no-prepare", action="store_true", help="No inicializar instance/ y DB (headless).")
    parser.add_argument(
        "--run",
        action="store_true",
        help="Abrir la app al final (sin preguntar). Si usas --no-install, abre el EXE construido.",
    )
    parser.add_argument("--clean", action="store_true", help="Borrar build/, dist/, dist_installer/ antes.")
    parser.add_argument("--onedir", action="store_true", help="Construir app en modo onedir (default: onefile).")
    parser.add_argument(
        "--install-dir",
        default="",
        help="Directorio destino (default: %%LOCALAPPDATA%%/Inventarios_POS).",
    )
    parser.add_argument(
        "--app-exe",
        default="",
        help="Ruta al EXE ya construido para instalar (si no, usa dist/InventariosPOS.exe).",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()

    if args.clean:
        _clean_build_artifacts(repo_root)

    # Choose python
    py = Path(sys.executable)
    venv_dir = (repo_root / ".venv").resolve()
    if not args.no_venv:
        py = _ensure_venv(venv_dir)

    # Dependencies
    if not args.no_deps:
        _pip_install(py, (repo_root / "requirements.txt").resolve())
        _pip_install(py, (repo_root / "requirements-dev.txt").resolve())

    # Prepare runtime (instance + sqlite schema)
    if not args.no_prepare:
        _prepare_runtime(py, repo_root)

    # Build
    built_app_exe: Path | None = None
    built_server_exe: Path | None = None
    if not args.no_build:
        built_app_exe = _build_app_exe(py, repo_root, onefile=not args.onedir)
        built_server_exe = _build_server_exe(py, repo_root, onefile=not args.onedir)
        _build_installer_exe(py, repo_root, built_app_exe, built_server_exe)

    # Install (copy EXE + shortcuts)
    installed_exe: Path | None = None
    if not args.no_install:
        if args.app_exe:
            source_exe = Path(args.app_exe).expanduser().resolve()
        elif built_app_exe:
            source_exe = built_app_exe
        else:
            # fallback to dist
            source_exe = (repo_root / "dist" / f"{APP_BUILD_NAME}.exe").resolve()

        install_dir = Path(args.install_dir).expanduser().resolve() if args.install_dir else _default_install_dir()
        server_source = built_server_exe
        if server_source is None:
            server_source = (repo_root / "dist" / f"{SERVER_BUILD_NAME}.exe").resolve()
            if not server_source.exists():
                server_source = None
        _install_from_exe(source_exe, install_dir, launch=True if args.run else None, server_source_exe=server_source)
        installed_exe = (install_dir / APP_EXE_CANONICAL_NAME).resolve()

    # Run without install: launch built EXE if available.
    if args.run and args.no_install:
        to_run = built_app_exe or (repo_root / "dist" / f"{APP_BUILD_NAME}.exe").resolve()
        if to_run.exists():
            subprocess.Popen([str(to_run)], cwd=str(to_run.parent))
        else:
            raise FileNotFoundError("No encontré el EXE para abrir. Quita --no-build o provee --app-exe.")

    return 0


def main() -> int:
    try:
        # Frozen => behave as real installer.
        if _is_frozen():
            install_dir = _default_install_dir()
            src_exe = _find_source_app_exe()
            _install_from_exe(src_exe, install_dir)
            return 0

        # Source => bootstrap/build/install.
        return _bootstrap_cli(sys.argv[1:])
    except Exception as e:
        # Always emit something to stderr so failures are visible even if GUI message boxes are not.
        try:
            import traceback

            traceback.print_exc()
        except Exception:
            pass
        _msgbox(
            f"No se pudo completar el proceso.\n\nDetalle: {e}",
            APP_DISPLAY_NAME,
            0x10,  # MB_ICONERROR
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
