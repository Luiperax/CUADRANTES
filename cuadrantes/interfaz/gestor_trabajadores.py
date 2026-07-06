"""
Diálogo de gestión de la plantilla de trabajadores.

Permite dar de alta, modificar y desactivar trabajadores, así como configurar sus
restricciones individuales (puestos habilitados de día y de noche, prohibición de
noches y preferencias) sin tocar el código.
"""

from __future__ import annotations

from PySide6 import QtWidgets

from ..config.constantes import Puesto
from ..datos.modelos import Trabajador
from ..servicio import ServicioCuadrantes


class DialogoTrabajador(QtWidgets.QDialog):
    """Formulario de alta/edición de un trabajador."""

    def __init__(self, trabajador: Trabajador | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trabajador")
        self.resize(420, 480)
        self.trabajador = trabajador or Trabajador(id=None, nombre="")

        disp = QtWidgets.QFormLayout(self)
        self.w_nombre = QtWidgets.QLineEdit(self.trabajador.nombre)
        self.w_activo = QtWidgets.QCheckBox()
        self.w_activo.setChecked(self.trabajador.activo)
        self.w_cm = QtWidgets.QDoubleSpinBox()
        self.w_cm.setRange(0, 400)
        self.w_cm.setValue(self.trabajador.computo_mensual)
        self.w_noches = QtWidgets.QCheckBox()
        self.w_noches.setChecked(self.trabajador.puede_hacer_noches)
        self.w_pref_dia = QtWidgets.QCheckBox()
        self.w_pref_dia.setChecked(self.trabajador.prefiere_turno_dia)
        self.w_pref_noche = QtWidgets.QCheckBox()
        self.w_pref_noche.setChecked(self.trabajador.prefiere_turno_noche)

        disp.addRow("Nombre:", self.w_nombre)
        disp.addRow("Activo:", self.w_activo)
        disp.addRow("Cómputo mensual:", self.w_cm)
        disp.addRow("Puede hacer noches:", self.w_noches)

        # Casillas de puestos diurnos y nocturnos.
        self.chk_diurnos = {}
        grupo_d = QtWidgets.QGroupBox("Puestos diurnos permitidos (MT)")
        ld = QtWidgets.QHBoxLayout(grupo_d)
        for p in Puesto:
            chk = QtWidgets.QCheckBox(p.value)
            chk.setChecked(p in self.trabajador.puestos_diurnos_permitidos)
            self.chk_diurnos[p] = chk
            ld.addWidget(chk)
        disp.addRow(grupo_d)

        self.chk_nocturnos = {}
        grupo_n = QtWidgets.QGroupBox("Puestos nocturnos permitidos (TN)")
        ln = QtWidgets.QHBoxLayout(grupo_n)
        for p in (Puesto.F1, Puesto.F2):
            chk = QtWidgets.QCheckBox(p.value)
            chk.setChecked(p in self.trabajador.puestos_nocturnos_permitidos)
            self.chk_nocturnos[p] = chk
            ln.addWidget(chk)
        disp.addRow(grupo_n)

        disp.addRow("Prefiere turno de día:", self.w_pref_dia)
        disp.addRow("Prefiere turno de noche:", self.w_pref_noche)
        self.w_notas = QtWidgets.QPlainTextEdit(self.trabajador.notas)
        disp.addRow("Notas:", self.w_notas)

        botones = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        disp.addRow(botones)

    def trabajador_resultante(self) -> Trabajador:
        t = self.trabajador
        t.nombre = self.w_nombre.text().strip()
        t.activo = self.w_activo.isChecked()
        t.computo_mensual = self.w_cm.value()
        t.puede_hacer_noches = self.w_noches.isChecked()
        t.prefiere_turno_dia = self.w_pref_dia.isChecked()
        t.prefiere_turno_noche = self.w_pref_noche.isChecked()
        t.puestos_diurnos_permitidos = {p for p, c in self.chk_diurnos.items() if c.isChecked()}
        t.puestos_nocturnos_permitidos = {p for p, c in self.chk_nocturnos.items() if c.isChecked()}
        t.notas = self.w_notas.toPlainText()
        return t


class GestorTrabajadores(QtWidgets.QDialog):
    """Lista de trabajadores con acciones de alta/edición/baja."""

    def __init__(self, servicio: ServicioCuadrantes, parent=None):
        super().__init__(parent)
        self.servicio = servicio
        self.setWindowTitle("Gestión de trabajadores")
        self.resize(560, 460)

        disp = QtWidgets.QVBoxLayout(self)
        self.lista = QtWidgets.QListWidget()
        disp.addWidget(self.lista)

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
        self.lista.clear()
        for t in self.servicio.trabajadores.listar():
            estado = "" if t.activo else "  (inactivo)"
            item = QtWidgets.QListWidgetItem(f"{t.nombre}{estado}")
            item.setData(256, t.id)
            self.lista.addItem(item)

    def _seleccionado(self) -> int | None:
        item = self.lista.currentItem()
        return item.data(256) if item else None

    def nuevo(self) -> None:
        dialogo = DialogoTrabajador(parent=self)
        if dialogo.exec() == QtWidgets.QDialog.Accepted:
            self.servicio.trabajadores.guardar(dialogo.trabajador_resultante())
            self.recargar()

    def editar(self) -> None:
        tid = self._seleccionado()
        if tid is None:
            return
        trabajador = self.servicio.trabajadores.obtener(tid)
        dialogo = DialogoTrabajador(trabajador, parent=self)
        if dialogo.exec() == QtWidgets.QDialog.Accepted:
            self.servicio.trabajadores.guardar(dialogo.trabajador_resultante())
            self.recargar()

    def eliminar(self) -> None:
        tid = self._seleccionado()
        if tid is None:
            return
        if QtWidgets.QMessageBox.question(
            self, "Confirmar", "¿Eliminar el trabajador seleccionado?"
        ) == QtWidgets.QMessageBox.Yes:
            self.servicio.trabajadores.eliminar(tid)
            self.recargar()
