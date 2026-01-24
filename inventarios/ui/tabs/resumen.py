from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from inventarios.repos import SalesRepo
from inventarios.ui.formatting import money_es


class ResumenTab(QtWidgets.QWidget):
    def __init__(self, session_factory):
        super().__init__()
        self._session_factory = session_factory
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        top = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("Actualizar")
        self.refresh_btn.clicked.connect(self.reload)
        top.addWidget(self.refresh_btn)
        top.addStretch(1)
        layout.addLayout(top)

        self.summary = QtWidgets.QLabel("—")
        f = self.summary.font()
        f.setPointSize(max(12, f.pointSize() + 2))
        f.setBold(True)
        self.summary.setFont(f)
        layout.addWidget(self.summary)

        split = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        self.sales_table = QtWidgets.QTableWidget(0, 3)
        self.sales_table.setHorizontalHeaderLabels(["Venta #", "Fecha", "Total"])
        self.sales_table.horizontalHeader().setStretchLastSection(True)
        self.sales_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.top_table = QtWidgets.QTableWidget(0, 3)
        self.top_table.setHorizontalHeaderLabels(["Producto", "Cantidad", "Total"])
        self.top_table.horizontalHeader().setStretchLastSection(True)
        self.top_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        split.addWidget(self.sales_table)
        split.addWidget(self.top_table)
        split.setSizes([350, 250])

        layout.addWidget(split, 1)

    def reload(self) -> None:
        with self._session_factory() as session:
            repo = SalesRepo(session)
            total = float(repo.total_sold())
            sales = repo.list_sales(limit=200)
            top = repo.top_products(limit=15)

        self.summary.setText(f"Total vendido histórico: ${money_es(total)}")

        self.sales_table.setRowCount(0)
        for s in sales:
            row = self.sales_table.rowCount()
            self.sales_table.insertRow(row)
            self.sales_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(s.id)))
            self.sales_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(s.created_at)))
            self.sales_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(s.total)))

        self.top_table.setRowCount(0)
        for t in top:
            row = self.top_table.rowCount()
            self.top_table.insertRow(row)
            self.top_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(t.producto)))
            self.top_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(t.qty)))
            self.top_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(t.total)))
