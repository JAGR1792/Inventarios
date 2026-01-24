from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from inventarios.repos import ProductRepo
from inventarios.services import PosService
from inventarios.ui.formatting import money_es


@dataclass(frozen=True)
class ProductVM:
    key: str
    producto: str
    descripcion: str
    unidades: int
    precio_final: float
    image_path: str | None


class ProductsTableModel(QtCore.QAbstractTableModel):
    COLS = ["Producto", "Descripción", "Stock", "Precio"]

    def __init__(self):
        super().__init__()
        self._items: list[ProductVM] = []

    def set_items(self, items: list[ProductVM]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.COLS)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        p = self._items[index.row()]

        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0:
                return p.producto
            if index.column() == 1:
                return p.descripcion
            if index.column() == 2:
                return str(p.unidades)
            if index.column() == 3:
                return "$" + money_es(p.precio_final)

        if role == QtCore.Qt.TextAlignmentRole:
            if index.column() in (2, 3):
                return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        if role == QtCore.Qt.ForegroundRole and index.column() == 2:
            if p.unidades <= 0:
                return QtGui.QBrush(QtGui.QColor("#b91c1c"))
            if p.unidades <= 2:
                return QtGui.QBrush(QtGui.QColor("#92400e"))

        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):  # noqa: N802
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self.COLS[section]
        return str(section + 1)

    def item_at(self, row: int) -> ProductVM | None:
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]


class CartTableModel(QtCore.QAbstractTableModel):
    COLS = ["Producto", "Cant", "Precio", "Total"]

    def __init__(self):
        super().__init__()
        self._lines: list[tuple[str, str, int, float]] = []  # key, name, qty, unit

    def set_lines(self, lines: list[tuple[str, str, int, float]]) -> None:
        self.beginResetModel()
        self._lines = list(lines)
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._lines)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.COLS)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        key, name, qty, unit = self._lines[index.row()]
        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0:
                return name
            if index.column() == 1:
                return str(qty)
            if index.column() == 2:
                return "$" + money_es(unit)
            if index.column() == 3:
                return "$" + money_es(float(qty) * float(unit))

        if role == QtCore.Qt.TextAlignmentRole:
            if index.column() in (1, 2, 3):
                return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):  # noqa: N802
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self.COLS[section]
        return str(section + 1)

    def key_at(self, row: int) -> str | None:
        if row < 0 or row >= len(self._lines):
            return None
        return self._lines[row][0]


class VentasTab(QtWidgets.QWidget):
    def __init__(self, session_factory):
        super().__init__()
        self._session_factory = session_factory

        self._products: dict[str, ProductVM] = {}
        self._cart: dict[str, int] = defaultdict(int)

        self._build_ui()
        self.reload_products()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        top = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Buscar o escanear (F2). Enter agrega el primero")
        self.search.textChanged.connect(self._debounced_search)

        self.import_btn = QtWidgets.QPushButton("Importar Excel")
        self.import_btn.clicked.connect(self._import_excel)

        self.refresh_btn = QtWidgets.QPushButton("Refrescar")
        self.refresh_btn.clicked.connect(self.reload_products)

        self.checkout_btn = QtWidgets.QPushButton("Cobrar (F4)")
        self.checkout_btn.clicked.connect(self.checkout)

        self.clear_btn = QtWidgets.QPushButton("Vaciar")
        self.clear_btn.clicked.connect(self.clear_cart)

        top.addWidget(self.search, 1)
        top.addWidget(self.import_btn)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.checkout_btn)
        top.addWidget(self.clear_btn)
        layout.addLayout(top)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)

        self.products_model = ProductsTableModel()
        self.products_view = QtWidgets.QTableView()
        self.products_view.setModel(self.products_model)
        self.products_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.products_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.products_view.doubleClicked.connect(self._add_selected_product)
        self.products_view.selectionModel().selectionChanged.connect(self._on_product_selected)
        self.products_view.horizontalHeader().setStretchLastSection(True)

        self.add_btn = QtWidgets.QPushButton("Agregar")
        self.add_btn.clicked.connect(self._add_selected_product)

        img_row = QtWidgets.QHBoxLayout()
        self.image_label = QtWidgets.QLabel("(Sin imagen)")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumHeight(180)
        self.image_label.setStyleSheet("border:1px solid #ddd; border-radius:8px; background:#fafafa;")

        self.set_image_btn = QtWidgets.QPushButton("Asignar imagen")
        self.set_image_btn.clicked.connect(self.assign_image)

        img_row.addWidget(self.image_label, 1)
        img_row.addWidget(self.set_image_btn)

        left_layout.addWidget(self.products_view, 1)
        left_layout.addWidget(self.add_btn)
        left_layout.addLayout(img_row)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)

        self.cart_model = CartTableModel()
        self.cart_view = QtWidgets.QTableView()
        self.cart_view.setModel(self.cart_model)
        self.cart_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.cart_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.cart_view.horizontalHeader().setStretchLastSection(True)

        btns = QtWidgets.QHBoxLayout()
        self.minus_btn = QtWidgets.QPushButton("-")
        self.minus_btn.clicked.connect(self.decrement_selected_cart)
        self.plus_btn = QtWidgets.QPushButton("+")
        self.plus_btn.clicked.connect(self.increment_selected_cart)
        self.remove_btn = QtWidgets.QPushButton("Quitar")
        self.remove_btn.clicked.connect(self.remove_selected_cart)
        btns.addWidget(self.minus_btn)
        btns.addWidget(self.plus_btn)
        btns.addWidget(self.remove_btn)
        btns.addStretch(1)

        self.total_label = QtWidgets.QLabel("TOTAL: $0,00")
        f = self.total_label.font()
        f.setPointSize(max(12, f.pointSize() + 4))
        f.setBold(True)
        self.total_label.setFont(f)

        self.error_label = QtWidgets.QLabel("")
        self.error_label.setStyleSheet("color:#b91c1c;")
        self.error_label.setWordWrap(True)

        right_layout.addWidget(self.cart_view, 1)
        right_layout.addLayout(btns)
        right_layout.addWidget(self.total_label)
        right_layout.addWidget(self.error_label)

        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([700, 500])
        layout.addWidget(split, 1)

        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)

        QtGui.QShortcut(QtGui.QKeySequence("F2"), self, activated=self._focus_search)
        QtGui.QShortcut(QtGui.QKeySequence("F4"), self, activated=self.checkout)
        QtGui.QShortcut(QtGui.QKeySequence("Return"), self, activated=self._add_first_result)

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def _debounced_search(self, _text: str) -> None:
        self._search_timer.start(120)

    def _apply_search(self) -> None:
        self.reload_products()

    def reload_products(self) -> None:
        self.error_label.setText("")
        q = self.search.text().strip()
        with self._session_factory() as session:
            repo = ProductRepo(session)
            rows = repo.list(q=q, limit=400)
            items: list[ProductVM] = []
            for r in rows:
                items.append(
                    ProductVM(
                        key=r.key,
                        producto=r.producto,
                        descripcion=r.descripcion or "",
                        unidades=int(r.unidades or 0),
                        precio_final=float(r.precio_final or 0),
                        image_path=repo.get_image(r.key),
                    )
                )
        self._products = {p.key: p for p in items}
        self.products_model.set_items(items)
        self.products_view.resizeColumnsToContents()
        self._sync_cart_view()

    def _selected_product(self) -> ProductVM | None:
        sel = self.products_view.selectionModel().selectedRows()
        if not sel:
            return None
        return self.products_model.item_at(sel[0].row())

    def _add_selected_product(self) -> None:
        p = self._selected_product()
        if p:
            self._add_to_cart(p.key)

    def _add_first_result(self) -> None:
        p = self.products_model.item_at(0)
        if p:
            self._add_to_cart(p.key)
            self._focus_search()

    def _add_to_cart(self, key: str) -> None:
        p = self._products.get(key)
        if not p:
            return
        if p.unidades <= 0:
            QtWidgets.QMessageBox.warning(self, "Sin stock", "Este producto no tiene stock.")
            return
        self._cart[key] += 1
        self._sync_cart_view()

    def _sync_cart_view(self) -> None:
        lines: list[tuple[str, str, int, float]] = []
        total = 0.0
        for key, qty in sorted(self._cart.items()):
            if qty <= 0:
                continue
            p = self._products.get(key)
            if not p:
                continue
            lines.append((key, p.producto, int(qty), float(p.precio_final)))
            total += float(qty) * float(p.precio_final)
        self.cart_model.set_lines(lines)
        self.cart_view.resizeColumnsToContents()
        self.total_label.setText(f"TOTAL: ${money_es(total)}")

    def _selected_cart_key(self) -> str | None:
        sel = self.cart_view.selectionModel().selectedRows()
        if not sel:
            return None
        return self.cart_model.key_at(sel[0].row())

    def increment_selected_cart(self) -> None:
        key = self._selected_cart_key()
        if key:
            self._add_to_cart(key)

    def decrement_selected_cart(self) -> None:
        key = self._selected_cart_key()
        if not key:
            return
        self._cart[key] = max(0, int(self._cart[key]) - 1)
        if self._cart[key] <= 0:
            self._cart.pop(key, None)
        self._sync_cart_view()

    def remove_selected_cart(self) -> None:
        key = self._selected_cart_key()
        if key:
            self._cart.pop(key, None)
            self._sync_cart_view()

    def clear_cart(self) -> None:
        self._cart.clear()
        self._sync_cart_view()

    def checkout(self) -> None:
        if not self._cart:
            return
        self.error_label.setText("")
        cart_payload = {k: int(q) for k, q in self._cart.items() if q > 0}
        with self._session_factory() as session:
            svc = PosService(session)
            res = svc.checkout(cart_payload)
            if not res.ok:
                self.error_label.setText(res.error or "Error")
                return

            sale_id = res.sale_id
            total = res.total or Decimal("0.00")

        QtWidgets.QMessageBox.information(
            self,
            "Venta registrada",
            f"Venta #{sale_id}\nTotal: {total}",
        )
        self._cart.clear()
        self.reload_products()

    def _on_product_selected(self) -> None:
        p = self._selected_product()
        if not p:
            self.image_label.setText("(Sin imagen)")
            self.image_label.setPixmap(QtGui.QPixmap())
            return

        if p.image_path and Path(p.image_path).exists():
            pix = QtGui.QPixmap(p.image_path)
            if not pix.isNull():
                self.image_label.setPixmap(
                    pix.scaled(240, 180, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                )
                self.image_label.setText("")
                return

        self.image_label.setPixmap(QtGui.QPixmap())
        self.image_label.setText("(Sin imagen)")

    def assign_image(self) -> None:
        p = self._selected_product()
        if not p:
            return
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Elegir imagen",
            str(Path.cwd()),
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not file_name:
            return
        with self._session_factory() as session:
            repo = ProductRepo(session)
            repo.set_image(p.key, file_name)
        self.reload_products()

    def _import_excel(self) -> None:
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Importar desde Excel",
            str(Path.cwd()),
            "Excel (*.xlsx)",
        )
        if not file_name:
            return

        from inventarios.excel_import import ExcelImporter
        from inventarios.repos import ProductRepo
        from inventarios.settings import Settings

        try:
            settings = Settings()
            with self._session_factory() as session:
                importer = ExcelImporter(
                    xlsx_path=Path(file_name),
                    worksheet_name=settings.EXCEL_WORKSHEET_NAME,
                    engine=settings.LOCAL_EXCEL_ENGINE,
                    cache_dir=settings.INSTANCE_DIR,
                )
                products = importer.read_products()
                repo = ProductRepo(session)
                repo.upsert_many(products)
            self.reload_products()
            QtWidgets.QMessageBox.information(self, "Importación OK", f"Importados: {len(products)}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error importando", str(e))
