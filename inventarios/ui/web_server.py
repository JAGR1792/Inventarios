from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, jsonify, redirect, request, send_from_directory

from inventarios.settings import Settings
from inventarios.ui.webview_backend import WebviewBackend


def _resolve_web_dir() -> Path:
    # In dev, this module lives in inventarios/ui; web assets are in inventarios/ui/web
    return (Path(__file__).resolve().parent / "web").resolve()


def create_app(session_factory, settings: Settings) -> Flask:
    web_dir = _resolve_web_dir()
    if not web_dir.exists():
        raise FileNotFoundError(f"Web UI not found: {web_dir}")

    # Expose images in a safe, narrow way (only INSTANCE_DIR/IMAGES_DIR)
    images_dir = (settings.INSTANCE_DIR / str(settings.IMAGES_DIR)).resolve()
    images_dir.mkdir(parents=True, exist_ok=True)

    backend = WebviewBackend(session_factory=session_factory, settings=settings)

    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def root() -> Response:
        return redirect("/store.html")

    @app.get("/health")
    def health() -> Response:
        return jsonify({"ok": True, "app": settings.APP_NAME})

    # --- Static UI files ---
    @app.get("/<path:filename>")
    def web_static(filename: str):
        # Avoid shadowing API/files endpoints
        if filename.startswith("api/") or filename.startswith("files/"):
            return jsonify({"ok": False, "error": "Not found"}), 404

        p = (web_dir / filename).resolve()
        if not str(p).startswith(str(web_dir)):
            return jsonify({"ok": False, "error": "Not found"}), 404
        if not p.exists() or not p.is_file():
            return jsonify({"ok": False, "error": "Not found"}), 404

        # Ensure correct content types for .js/.css on some Windows setups
        if p.suffix.lower() in (".js", ".css"):
            mimetypes.add_type("application/javascript", ".js")
            mimetypes.add_type("text/css", ".css")

        return send_from_directory(web_dir, filename)

    # --- Files (images) ---
    @app.get("/files/images/<path:filename>")
    def files_images(filename: str):
        p = (images_dir / filename).resolve()
        if not str(p).startswith(str(images_dir)):
            return jsonify({"ok": False, "error": "Not found"}), 404
        if not p.exists() or not p.is_file():
            return jsonify({"ok": False, "error": "Not found"}), 404
        return send_from_directory(images_dir, filename)

    def _ok(payload):
        return jsonify(payload)

    # --- JSON API ---
    @app.get("/api/getAppInfo")
    def api_get_app_info():
        info = backend.getAppInfo()
        # When using HTTP, show a more useful db_file if present.
        return _ok(info)

    @app.post("/api/searchProducts")
    def api_search_products():
        data = request.get_json(silent=True) or {}
        q = data.get("q", "")
        limit = data.get("limit", 180)
        rows = backend.searchProducts(q, limit)

        # Convert file:// image urls to http-served urls when possible.
        out = []
        for r in (rows or []):
            rr = dict(r)
            img = rr.get("image_url")
            if isinstance(img, str) and img.startswith("file:"):
                # Backend stores absolute paths in DB; we only serve filenames inside images_dir.
                try:
                    # file:///C:/path/to/file.png?v=123
                    before_q = img.split("?", 1)[0]
                    filename = Path(before_q).name
                    if filename:
                        rr["image_url"] = f"/files/images/{quote(filename)}" + ("?" + img.split("?", 1)[1] if "?" in img else "")
                except Exception:
                    pass
            out.append(rr)
        return _ok(out)

    @app.get("/api/getCategories")
    def api_get_categories():
        return _ok(backend.getCategories())

    @app.post("/api/checkout")
    def api_checkout():
        data = request.get_json(silent=True) or {}
        return _ok(backend.checkout(data.get("lines"), data.get("payment")))

    @app.get("/api/getSummary")
    def api_get_summary():
        limit = request.args.get("limit", "25")
        return _ok(backend.getSummary(int(limit)))

    @app.get("/api/listCashCloses")
    def api_list_cash_closes():
        limit = request.args.get("limit", "30")
        return _ok(backend.listCashCloses(int(limit)))

    @app.get("/api/getCashPanel")
    def api_get_cash_panel():
        day = request.args.get("day", "")
        return _ok(backend.getCashPanel(day))

    @app.post("/api/useSuggestedOpeningCash")
    def api_use_suggested_opening_cash():
        data = request.get_json(silent=True) or {}
        return _ok(backend.useSuggestedOpeningCash(data.get("day")))

    @app.post("/api/setOpeningCash")
    def api_set_opening_cash():
        data = request.get_json(silent=True) or {}
        return _ok(backend.setOpeningCash(data.get("day"), data.get("opening_cash")))

    @app.post("/api/addCashWithdrawal")
    def api_add_cash_withdrawal():
        data = request.get_json(silent=True) or {}
        return _ok(backend.addCashWithdrawal(data.get("day"), data.get("amount"), data.get("notes", "")))

    @app.post("/api/deleteCashMove")
    def api_delete_cash_move():
        data = request.get_json(silent=True) or {}
        return _ok(backend.deleteCashMove(data.get("id")))

    @app.post("/api/closeCashDay")
    def api_close_cash_day():
        data = request.get_json(silent=True) or {}
        return _ok(
            backend.closeCashDay(
                data.get("day"),
                data.get("cash_counted"),
                data.get("carry_to_next_day"),
                data.get("notes", ""),
                bool(data.get("force")),
            )
        )

    @app.post("/api/setProductCategory")
    def api_set_product_category():
        data = request.get_json(silent=True) or {}
        return _ok(backend.setProductCategory(data.get("key"), data.get("category")))

    @app.post("/api/clearProductImage")
    def api_clear_product_image():
        data = request.get_json(silent=True) or {}
        return _ok(backend.clearProductImage(data.get("key")))

    @app.post("/api/restockProduct")
    def api_restock_product():
        data = request.get_json(silent=True) or {}
        return _ok(backend.restockProduct(data.get("key"), data.get("delta"), data.get("notes", "")))

    @app.post("/api/setProductStock")
    def api_set_product_stock():
        data = request.get_json(silent=True) or {}
        return _ok(backend.setProductStock(data.get("key"), data.get("stock"), data.get("notes", "")))

    @app.post("/api/setProductPrice")
    def api_set_product_price():
        data = request.get_json(silent=True) or {}
        return _ok(backend.setProductPrice(data.get("key"), data.get("precio_final")))

    @app.post("/api/createProduct")
    def api_create_product():
        data = request.get_json(silent=True) or {}
        return _ok(
            backend.createProduct(
                data.get("producto"),
                data.get("descripcion", ""),
                data.get("precio_final"),
                data.get("unidades", 0),
                data.get("category", ""),
            )
        )

    @app.post("/api/resetDatabase")
    def api_reset_db():
        data = request.get_json(silent=True) or {}
        return _ok(backend.resetDatabase(data.get("confirm_text", "")))

    @app.post("/api/openImagesFolder")
    def api_open_images_folder():
        # Works only on the server machine (Windows); tablet users just get the path.
        return _ok(backend.openImagesFolder())

    # --- Upload endpoints (tablet-friendly) ---
    @app.post("/api/uploadProductImage")
    def api_upload_product_image():
        key = (request.form.get("key") or "").strip()
        f = request.files.get("file")
        if not key:
            return _ok({"ok": False, "error": "Producto inválido"})
        if f is None or not f.filename:
            return _ok({"ok": False, "error": "Archivo inválido"})

        # Save with the same naming strategy as desktop (safe filename) but keep ext.
        ext = Path(f.filename).suffix.lower() or ".png"
        safe_key = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in key).strip("_.") or "img"
        dst = images_dir / f"{safe_key}{ext}"
        try:
            f.save(dst)
        except Exception as e:
            return _ok({"ok": False, "error": f"No se pudo guardar imagen: {e}"})

        # Reuse backend logic to map the image in DB
        try:
            # This calls ProductRepo.set_image
            from inventarios.db import session_scope
            from inventarios.repos import ProductRepo

            with session_scope(session_factory) as session:
                repo = ProductRepo(session)
                repo.set_image(key, str(dst))
        except Exception as e:
            return _ok({"ok": False, "error": f"No se pudo guardar mapeo: {e}"})

        # Cache-bust
        v = ""
        try:
            v = f"?v={int(dst.stat().st_mtime_ns)}"
        except Exception:
            v = ""

        return _ok({"ok": True, "image_url": f"/files/images/{quote(dst.name)}{v}"})

    @app.post("/api/importExcelUpload")
    def api_import_excel_upload():
        f = request.files.get("file")
        if f is None or not f.filename:
            return _ok({"ok": False, "error": "Archivo inválido"})

        tmp = (settings.INSTANCE_DIR / "_upload.xlsx").resolve()
        try:
            f.save(tmp)
        except Exception as e:
            return _ok({"ok": False, "error": f"No se pudo guardar Excel: {e}"})

        try:
            res = backend._settings  # keep lint quiet
            # Use the same importer as desktop, but with the uploaded file.
            from inventarios.excel_import import ExcelImporter
            from inventarios.db import session_scope
            from inventarios.repos import ProductRepo

            importer = ExcelImporter(
                xlsx_path=tmp,
                worksheet_name=settings.EXCEL_WORKSHEET_NAME,
                engine="openpyxl",  # server-side safe default
                cache_dir=settings.INSTANCE_DIR,
            )
            products = importer.read_products()
            if not products:
                return _ok({"ok": False, "error": "No se encontraron productos (revisa hoja/encabezados)."})

            with session_scope(session_factory) as session:
                repo = ProductRepo(session)
                changed = repo.upsert_many(products)

            return _ok({"ok": True, "imported": int(len(products)), "upserted": int(changed)})
        except Exception as e:
            return _ok({"ok": False, "error": str(e)})
        finally:
            try:
                tmp.unlink(missing_ok=True)  # py3.8+ supports missing_ok
            except Exception:
                pass

    return app
