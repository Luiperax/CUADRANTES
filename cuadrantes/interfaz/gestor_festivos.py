"""
Gestión de festivos.

Permite revisar y ajustar los festivos de cada año. Incluye un botón para cargar
automáticamente el calendario oficial de la comunidad y el municipio configurados
(por defecto, Madrid), y opciones para añadir, editar o eliminar festivos
manualmente (por si algún año la fecha oficial cambia).
"""

from __future__ import annotations

from datetime import date

from PySide6 import QtCore, QtWidgets

from ..datos.modelos import Festivo
from ..servicio import ServicioCuadrantes


class DialogoFestivo(QtWidgets.QDialog):
    """Alta o edición de un festivo (fecha + descripción)."""

    def __init__(self, festivo: Festivo | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Festivo")
        self.festivo = festivo
        disp = QtWidgets.QFormLayout(self)

        self.w_fecha = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.w_fecha.setCalendarPopup(True)
        self.w_fecha.setDisplayFormat("dd/MM/yyyy")
        self.w_desc = QtWidgets.QLineEdit()
        if festivo:
            self.w_fecha.setDate(QtCore.QDate(festivo.fecha.year, festivo.fecha.month, festivo.fecha.day))
            self.w_desc.setText(festivo.descripcion)

        disp.addRow("Fecha:", self.w_fecha)
        disp.addRow("Descripción:", self.w_desc)
        botones = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        disp.addRow(botones)

    def festivo_resultante(self) -> Festivo:
        return Festivo(
            id=self.festivo.id if self.festivo else None,
            fecha=self.w_fecha.date().toPython(),
            descripcion=self.w_desc.text(),
        )


class GestorFestivos(QtWidgets.QDialog):
    """Lista de festivos con carga automática del calendario oficial."""

    def __init__(self, servicio: ServicioCuadrantes, parent=None):
        super().__init__(parent)
        self.servicio = servicio
        self.setWindowTitle("Festivos")
        self.resize(560, 520)

        disp = QtWidgets.QVBoxLayout(self)
        config = servicio.configuracion()
        disp.addWidget(QtWidgets.QLabel(
            f"Calendario configurado: {config.comunidad_autonoma} · {config.municipio}. "
            "Cargue los festivos oficiales del año y ajuste lo que necesite."))

        # Fila de carga del año.
        fila = QtWidgets.QHBoxLayout()
        self.spin_anio = QtWidgets.QSpinBox()
        self.spin_anio.setRange(2020, 2100)
        hoy = date.today()
        self.spin_anio.setValue(hoy.year + (1 if hoy.month >= 11 else 0))
        boton_cargar = QtWidgets.QPushButton("📅 Cargar festivos oficiales del año")
        boton_cargar.setObjectName("primario")
        boton_cargar.clicked.connect(self.cargar_oficiales)
        fila.addWidget(QtWidgets.QLabel("Año:"))
        fila.addWidget(self.spin_anio)
        fila.addWidget(boton_cargar)
        fila.addStretch()
        disp.addLayout(fila)

        self.tabla = QtWidgets.QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Fecha", "Descripción"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        disp.addWidget(self.tabla)

        botones = QtWidgets.QHBoxLayout()
        b_add = QtWidgets.QPushButton("➕ Nuevo")
        b_edit = QtWidgets.QPushButton("✏️ Editar")
        b_del = QtWidgets.QPushButton("🗑️ Eliminar")
        b_add.clicked.connect(self.nuevo)
        b_edit.clicked.connect(self.editar)
        b_del.clicked.connect(self.eliminar)
        for b in (b_add, b_edit, b_del):
            botones.addWidget(b)
        botones.addStretch()
        disp.addLayout(botones)
        self.recargar()

    def recargar(self) -> None:
        self.tabla.setRowCount(0)
        for festivo in self.servicio.festivos.listar_todos():
            f = self.tabla.rowCount()
            self.tabla.insertRow(f)
            item_fecha = QtWidgets.QTableWidgetItem(festivo.fecha.strftime("%d/%m/%Y"))
            item_fecha.setData(QtCore.Qt.UserRole, festivo.id)
            self.tabla.setItem(f, 0, item_fecha)
            self.tabla.setItem(f, 1, QtWidgets.QTableWidgetItem(festivo.descripcion))
        self.tabla.resizeColumnsToContents()

    def cargar_oficiales(self) -> None:
        anio = self.spin_anio.value()
        n = self.servicio.cargar_festivos_oficiales(anio)
        self.recargar()
        QtWidgets.QMessageBox.information(
            self, "Festivos cargados",
            f"Se han cargado {n} festivos oficiales de {anio}.\n"
            "Revise y ajuste si su calendario local difiere algún año.")

    def _festivo_seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        fid = self.tabla.item(fila, 0).data(QtCore.Qt.UserRole)
        return next((f for f in self.servicio.festivos.listar_todos() if f.id == fid), None)

    def nuevo(self) -> None:
        dialogo = DialogoFestivo(parent=self)
        if dialogo.exec() == QtWidgets.QDialog.Accepted:
            self.servicio.festivos.guardar(dialogo.festivo_resultante())
            self.recargar()

    def editar(self) -> None:
        festivo = self._festivo_seleccionado()
        if not festivo:
            return
        dialogo = DialogoFestivo(festivo, parent=self)
        if dialogo.exec() == QtWidgets.QDialog.Accepted:
            # Al cambiar la fecha se elimina el anterior y se guarda el nuevo.
            self.servicio.festivos.eliminar(festivo.id)
            self.servicio.festivos.guardar(dialogo.festivo_resultante())
            self.recargar()

    def eliminar(self) -> None:
        festivo = self._festivo_seleccionado()
        if not festivo:
            return
        if QtWidgets.QMessageBox.question(
            self, "Confirmar", f"¿Eliminar el festivo del {festivo.fecha.strftime('%d/%m/%Y')}?"
        ) == QtWidgets.QMessageBox.Yes:
            self.servicio.festivos.eliminar(festivo.id)
            self.recargar()
