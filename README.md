# POS Desktop (pywebview/WebView2) + SQLite

Este proyecto es un **POS de escritorio** (Point of Sale) hecho con **pywebview** (usa Edge WebView2 en Windows).

La **fuente de verdad** ahora es una **base de datos real** (SQLite), para máxima velocidad y estabilidad.
El Excel queda como **fuente de importación** (opcional) para cargar/actualizar catálogo.

## Objetivo clave
- Operación rápida tipo caja: búsqueda/escaneo, carrito, cobro.
- Persistencia local: ventas y stock quedan en SQLite.
- Importación desde Excel (si lo deseas): se leen solo columnas requeridas de la hoja `Costos`.

## Arquitectura (bien separada)

- `inventarios/`: core (settings, DB, modelos, repos, servicios, importador de Excel).
- `inventarios/ui/`: host desktop (pywebview) + UI web (HTML/CSS/JS).
- `main.py`: entrypoint desktop.

### Flujo de datos
1. (Opcional) **Importar catálogo** desde Excel a SQLite.
2. **Ventas/stock** se operan contra SQLite (rápido y consistente).
3. **Resumen** se calcula desde el historial local (SQLite).

## Excel (opcional): Importar catálogo
Puedes importar (o reimportar) productos desde un `.xlsx`:
- Hoja: `EXCEL_WORKSHEET_NAME` (default `Costos`)
- Columnas: `Producto`, `Descripcion`, `unidades`, `Precio Final`

Motor:
- `LOCAL_EXCEL_ENGINE=openpyxl` (rápido)
- `LOCAL_EXCEL_ENGINE=excel` (Windows + Excel instalado): mejor para valores de fórmulas

## Por qué no usar Excel como “base de datos”
Excel es excelente para planillas, pero como motor de datos es frágil (bloqueos al abrir, fórmulas no recalculadas por librerías, riesgo de corrupción, bajo rendimiento al leer/escribir).

SQLite es:
- Mucho más rápido para búsquedas.
- Seguro para transacciones (ventas/stock).
- Fácil de respaldar (un archivo).

## Configuración
Copia `.env.example` a `.env` y ajusta:
- `DATABASE_URL` (por defecto: `sqlite:///instance/pos.sqlite`)
- `EXCEL_IMPORT_PATH` (si vas a importar)
- `EXCEL_WORKSHEET_NAME` (por defecto: `Costos`)
- `LOCAL_EXCEL_ENGINE` (`openpyxl` o `excel`)
- `IMAGES_DIR` (opcional)

## Ejecutar
- Instalar deps: `pip install -r requirements.txt`
- (Opcional) Importar Excel → SQLite: `python scripts/import_excel_to_db.py`
- Iniciar desktop: `python run_desktop.py`

## Modo tablet (LAN / navegador)
Para usar el POS desde una tablet Android en la misma red (sin instalar nada en la tablet):

- Iniciar servidor web: `python run_server.py --host 0.0.0.0 --port 8000`
- En la tablet, abrir: `http://IP-DE-LA-PC:8000/store.html?lite=1`

Notas:
- `?lite=1` es recomendado para Android WebView (menos efectos, más fluido).
- La carpeta `instance/` guarda la DB e imágenes locales y **no se versiona**.

## Build (Windows .exe) (opcional)
Si quieres empaquetar para Windows, usa el script:

- `./scripts/build_exe.ps1`

Los artefactos `build/`, `dist/` y `dist_installer/` son **generados** y no se versionan.

Reiniciar base de datos (borra ventas/pruebas):
- UI: botón **Reiniciar DB** (pide escribir `BORRAR`)
- CLI: `python scripts/reset_db.py`

Manual para el dueño/a (imágenes y operación):
- [MANUAL_DUENA.md](MANUAL_DUENA.md)

## UI (pywebview + WebView2)
La interfaz es HTML/CSS/JS corriendo en Edge WebView2 embebido (rápido y con buena compatibilidad web).

Vistas:
- **Tienda**: grilla tipo catálogo.
- **Resumen del día**: total vendido y últimas ventas + histórico de cierres.
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
