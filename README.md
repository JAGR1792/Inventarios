# POS Desktop (pywebview/WebView2) + SQLite

Este proyecto es un **POS de escritorio** (Point of Sale) hecho con **pywebview** (usa Edge WebView2 en Windows).

La **fuente de verdad** ahora es una **base de datos real** (SQLite), para máxima velocidad y estabilidad.
La sincronización de inventario se hace con **Google Sheets**.

## Objetivo clave
- Operación rápida tipo caja: búsqueda/escaneo, carrito, cobro.
- Persistencia local: ventas y stock quedan en SQLite.
- Sincronización de inventario con Google Sheets: importar/exportar desde la app.

## Arquitectura (bien separada)

- `inventarios/`: core (settings, DB, modelos, repos, servicios).
- `inventarios/ui/`: host desktop (pywebview) + UI web (HTML/CSS/JS).
- `main.py`: entrypoint desktop.

### Flujo de datos
1. **Importar inventario** desde Google Sheets a SQLite.
2. **Ventas/stock** se operan contra SQLite (rápido y consistente).
3. **Resumen** se calcula desde el historial local (SQLite).

## 🔄 Google Sheets (opcional): Sincronización automática
**¡NUEVO!** Ahora puedes sincronizar el inventario con Google Sheets en tiempo real:
- ✅ Exportar inventario automáticamente a Google Sheets
- ✅ Importar cambios desde Google Sheets
- ✅ Acceso desde cualquier lugar con tu cuenta de Google
- ✅ Sincronización bidireccional

👉 **Ver guía completa**: [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)

SQLite es:
- Mucho más rápido para búsquedas.
- Seguro para transacciones (ventas/stock).
- Fácil de respaldar (un archivo).

## Configuración
Copia `.env.example` a `.env` y ajusta:
- `DATABASE_URL` (por defecto: `sqlite:///instance/pos.sqlite`)
- `IMAGES_DIR` (opcional)
- **Google Sheets** (opcional): Ver [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md) para sincronización automática

## Ejecutar
- Instalar deps: `pip install -r requirements.txt`
- (Opcional) Importar desde Google Sheets → SQLite: `python scripts/import_google_sheets_to_db.py`
- Iniciar desktop: `python run_desktop.py`

## Modo tablet (LAN / navegador)
Para usar el POS desde una tablet Android en la misma red (sin instalar nada en la tablet):

- Iniciar servidor web: `python run_server.py --host 0.0.0.0 --port 8000`
- En la tablet, abrir: `http://IP-DE-LA-PC:8000/store.html?lite=1`

### Doble clic (Windows) para iniciar el servidor (sin consola)
En este repo hay launchers listos para Windows:

- `IniciarServidorTablet_Oculto.vbs` (recomendado): inicia el servidor en segundo plano y muestra un mensaje con la URL.
- `IniciarServidorTablet.bat`: hace lo mismo y además abre `http://127.0.0.1:8000/` en el navegador.
- `DetenerServidorTablet.bat`: detiene el servidor (mata el proceso que escucha en el puerto 8000).

El log queda en `instance/server.log`.

Notas:
- `?lite=1` es recomendado para Android WebView (menos efectos, más fluido).
- La carpeta `instance/` guarda la DB e imágenes locales y **no se versiona**.

## Build (Windows .exe) (opcional)
Si quieres empaquetar para Windows, usa el script:

- `./scripts/build_exe.ps1`

Para el modo tablet como `.exe` (para que el instalador cree el acceso directo **Inventarios POS - Servidor Tablet**):

- `./scripts/build_server_exe.ps1`
- `./scripts/build_installer.ps1`

Los artefactos `build/`, `dist/` y `dist_installer/` son **generados** y no se versionan.

Reiniciar base de datos (borra ventas/pruebas):
- UI: botón **Reiniciar DB** (pide escribir `BORRAR`)
- CLI: `python scripts/reset_db.py`

Manual para el dueño/a (imágenes y operación):
- [MANUAL_DUENA.md](MANUAL_DUENA.md)

## UI (pywebview + WebView2)
La interfaz es HTML/CSS/JS corriendo en Edge WebView2 embebido (rápido y con buena compatibilidad web).

Vistas:
- **Tienda**: grilla tipo catálogo con scroll en carrito desktop.
- **Inventario**: gestión completa con scroll en modales largos, botón para limpiar duplicados.
- **Resumen del día**: 
  - 🏆 **Productos estrella** con slider horizontal (deslizable)
  - 📋 **Últimas ventas** con resumen de productos vendidos
  - 🔍 **Detalle de venta** expandible al hacer clic
  - 📊 **Menús desplegables** tipo acordeón para mejor organización
- **Caja (panel derecho fijo)**: ticket/checkout + cierre de caja del día.

Cierre de caja:
- Guarda **efectivo al iniciar**, **retiros** (dinero sacado durante el día), y el **cierre** con el efectivo esperado y el efectivo a dejar para el día siguiente.
- El día siguiente se precarga con el valor “Para mañana” del último cierre anterior.

Imágenes:
- Se mapean en SQLite (tabla `product_images`).
- Los archivos se guardan en `instance/product_images/` (configurable con `IMAGES_DIR`).
- En el modal del producto puedes **Cambiar imagen** o **Quitar imagen**.

Reiniciar DB:
- Borra ventas y movimientos de caja, y pone el stock en 0.
- **No borra imágenes** (ni archivos ni mapeos).

## Alcance
Este repo trae un esqueleto funcional mínimo. La UI es intencionalmente simple para priorizar arquitectura y flujo.
