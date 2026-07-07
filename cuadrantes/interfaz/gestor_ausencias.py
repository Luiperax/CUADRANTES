"""
Gestión de ausencias (vacaciones, bajas médicas y permisos).

Permite dar de alta, editar y eliminar ausencias en cualquier momento, sin
necesidad de pasar por el asistente de generación. Las ausencias registradas aquí
se tienen en cuenta automáticamente al generar el cuadrante del mes afectado.
"""

from __future__ import annotations

from datetime import date

from PySide6 import QtCore, QtWidgets

from ..config.constantes import TipoAusencia
from ..datos.modelos import Ausencia
from ..servicio import ServicioCuadrantes


# Tipos de ausencia ofrecidos en la interfaz (etiqueta -> tipo).
_TIPOS = [
    TipoAusencia.VACACIONES,
    TipoAusencia.BAJA_MEDICA,
    TipoAusencia.PERMISO_RETRIBUIDO,
    TipoAusencia.PERMISO_SIN_SUELDO,
    TipoAusencia.FORMACION,
    TipoAusencia.ASUNTOS_PROPIOS,
    TipoAusencia.LIBRE,   # Días libres solicitados expresamente por el trabajador.
]


class DialogoAusencia(QtWidgets.QDialog):
    """Formulario de alta/edición de una ausencia."""

    def __init__(self, trabajadores, ausencia: Ausencia | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ausencia")
        self.resize(420, 260)
        self.ausencia = ausencia
        self.trabajadores = trabajadores

        disp = QtWidgets.QFormLayout(self)
        self.w_trab = QtWidgets.QComboBox()
        for t in trabajadores:
            self.w_trab.addItem(t.nombre, t.id)
        self.w_tipo = QtWidgets.QComboBox()
        for tipo in _TIPOS:
            self.w_tipo.addItem(tipo.descripcion, tipo.value)
        self.w_inicio = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.w_inicio.setCalendarPopup(True)
        self.w_inicio.setDisplayFormat("dd/MM/yyyy")
        self.w_fin = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.w_fin.setCalendarPopup(True)
        self.w_fin.setDisplayFormat("dd/MM/yyyy")
        self.w_desc = QtWidgets.QLineEdit()

        if ausencia:
            idx = self.w_trab.findData(ausencia.trabajador_id)
            self.w_trab.setCurrentIndex(max(0, idx))
            idx_t = self.w_tipo.findData(ausencia.tipo.value)
            self.w_tipo.setCurrentIndex(max(0, idx_t))
            self.w_inicio.setDate(QtCore.QDate(ausencia.fecha_inicio.year,
                                               ausencia.fecha_inicio.month,
                                               ausencia.fecha_inicio.day))
            self.w_fin.setDate(QtCore.QDate(ausencia.fecha_fin.year,
                                            ausencia.fecha_fin.month,
                                            ausencia.fecha_fin.day))
            self.w_desc.setText(ausencia.descripcion)

        disp.addRow("Trabajador:", self.w_trab)
        disp.addRow("Tipo:", self.w_tipo)
        disp.addRow("Fecha de inicio:", self.w_inicio)
        disp.addRow("Fecha de fin:", self.w_fin)
        disp.addRow("Descripción:", self.w_desc)

        botones = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        disp.addRow(botones)

    def _validar_y_aceptar(self) -> None:
        if self.w_fin.date().toPython() < self.w_inicio.date().toPython():
            QtWidgets.QMessageBox.warning(
                self, "Fechas incorrectas",
                "La fecha de fin no puede ser anterior a la de inicio.")
            return
        self.accept()

    def ausencia_resultante(self) -> Ausencia:
        return Ausencia(
            id=self.ausencia.id if self.ausencia else None,
            trabajador_id=self.w_trab.currentData(),
            tipo=TipoAusencia(self.w_tipo.currentData()),
            fecha_inicio=self.w_inicio.date().toPython(),
            fecha_fin=self.w_fin.date().toPython(),
            descripcion=self.w_desc.text(),
        )


class GestorAusencias(QtWidgets.QDialog):
    """Lista de ausencias con acciones de alta/edición/baja."""

    def __init__(self, servicio: ServicioCuadrantes, parent=None):
        super().__init__(parent)
        self.servicio = servicio
        self.setWindowTitle("Vacaciones, bajas y permisos")
        self.resize(720, 480)

        disp = QtWidgets.QVBoxLayout(self)
        disp.addWidget(QtWidgets.QLabel(
            "Ausencias registradas. Se aplican automáticamente al generar el cuadrante "
            "del mes correspondiente."))
        self.tabla = QtWidgets.QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Trabajador", "Tipo", "Inicio", "Fin", "Descripción"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        disp.addWidget(self.tabla)

        botones = QtWidgets.QHBoxLayout()
        b_add = QtWidgets.QPushButton("➕ Nueva ausencia")
        b_add.setObjectName("primario")
        b_edit = QtWidgets.QPushButton("✏️ Editar")
        b_del = QtWidgets.QPushButton("🗑️ Eliminar")
        b_add.clicked.connect(self.nueva)
        b_edit.clicked.connect(self.editar)
        b_del.clicked.connect(self.eliminar)
        for b in (b_add, b_edit, b_del):
            botones.addWidget(b)
        botones.addStretch()
        disp.addLayout(botones)

        self._nombres = {t.id: t.nombre for t in self.servicio.trabajadores.listar()}
        self.recargar()

    def recargar(self) -> None:
        self.tabla.setRowCount(0)
        for ausencia in self.servicio.ausencias.listar_todas():
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = [
                self._nombres.get(ausencia.trabajador_id, str(ausencia.trabajador_id)),
                ausencia.tipo.descripcion,
                ausencia.fecha_inicio.strftime("%d/%m/%Y"),
                ausencia.fecha_fin.strftime("%d/%m/%Y"),
                ausencia.descripcion,
            ]
            for c, v in enumerate(valores):
                item = QtWidgets.QTableWidgetItem(v)
                if c == 0:
                    item.setData(QtCore.Qt.UserRole, ausencia.id)
                self.tabla.setItem(fila, c, item)
        self.tabla.resizeColumnsToContents()

    def _ausencia_seleccionada_id(self) -> int | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        return self.tabla.item(fila, 0).data(QtCore.Qt.UserRole)

    def nueva(self) -> None:
        trabajadores = self.servicio.trabajadores.listar(solo_activos=True)
        if not trabajadores:
            QtWidgets.QMessageBox.information(self, "Aviso", "No hay trabajadores activos.")
            return
        dialogo = DialogoAusencia(trabajadores, parent=self)
        if dialogo.exec() == QtWidgets.QDialog.Accepted:
            self.servicio.ausencias.guardar(dialogo.ausencia_resultante())
            self.recargar()

    def editar(self) -> None:
        aid = self._ausencia_seleccionada_id()
        if aid is None:
            return
        ausencia = next((a for a in self.servicio.ausencias.listar_todas() if a.id == aid), None)
        if not ausencia:
            return
        trabajadores = self.servicio.trabajadores.listar()
        dialogo = DialogoAusencia(trabajadores, ausencia, parent=self)
        if dialogo.exec() == QtWidgets.QDialog.Accepted:
            self.servicio.ausencias.guardar(dialogo.ausencia_resultante())
            self.recargar()

    def eliminar(self) -> None:
        aid = self._ausencia_seleccionada_id()
        if aid is None:
            return
        if QtWidgets.QMessageBox.question(
            self, "Confirmar", "¿Eliminar la ausencia seleccionada?"
        ) == QtWidgets.QMessageBox.Yes:
            self.servicio.ausencias.eliminar(aid)
            self.recargar()
