"""
Asistente previo a la generación del cuadrante.

Antes de generar cualquier cuadrante, la aplicación abre este asistente que
recaba obligatoriamente la información del mes: vacaciones, bajas médicas,
permisos, restricciones individuales e incidencias. Nunca se genera un cuadrante
sin pasar por aquí.
"""

from __future__ import annotations

from datetime import date

from PySide6 import QtCore, QtWidgets

from ..config.constantes import NOMBRES_MES, TipoAusencia
from ..datos.modelos import Ausencia, Incidencia, RestriccionTemporal
from ..servicio import ServicioCuadrantes


class _TablaPeriodos(QtWidgets.QWidget):
    """Editor genérico de filas «trabajador / fecha inicio / fecha fin»."""

    def __init__(self, servicio: ServicioCuadrantes, con_tipo: bool = False):
        super().__init__()
        self.servicio = servicio
        self.con_tipo = con_tipo
        self.trabajadores = servicio.trabajadores.listar(solo_activos=True)

        disposicion = QtWidgets.QVBoxLayout(self)
        columnas = ["Trabajador", "Inicio", "Fin"]
        if con_tipo:
            columnas.insert(1, "Tipo")
        self.tabla = QtWidgets.QTableWidget(0, len(columnas))
        self.tabla.setHorizontalHeaderLabels(columnas)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        disposicion.addWidget(self.tabla)

        botones = QtWidgets.QHBoxLayout()
        boton_add = QtWidgets.QPushButton("➕ Añadir")
        boton_del = QtWidgets.QPushButton("🗑️ Quitar")
        boton_add.clicked.connect(self.anadir_fila)
        boton_del.clicked.connect(self.quitar_fila)
        botones.addWidget(boton_add)
        botones.addWidget(boton_del)
        botones.addStretch()
        disposicion.addLayout(botones)

    def anadir_fila(self) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        combo = QtWidgets.QComboBox()
        for t in self.trabajadores:
            combo.addItem(t.nombre, t.id)
        col = 0
        self.tabla.setCellWidget(fila, col, combo)
        col += 1
        if self.con_tipo:
            combo_tipo = QtWidgets.QComboBox()
            for tipo in (TipoAusencia.PERMISO_RETRIBUIDO, TipoAusencia.PERMISO_SIN_SUELDO,
                         TipoAusencia.FORMACION, TipoAusencia.ASUNTOS_PROPIOS):
                combo_tipo.addItem(tipo.descripcion, tipo.value)
            self.tabla.setCellWidget(fila, col, combo_tipo)
            col += 1
        for c in (col, col + 1):
            editor = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd/MM/yyyy")
            self.tabla.setCellWidget(fila, c, editor)

    def quitar_fila(self) -> None:
        fila = self.tabla.currentRow()
        if fila >= 0:
            self.tabla.removeRow(fila)

    def recoger(self, tipo_por_defecto: TipoAusencia) -> list[tuple]:
        """Devuelve la lista de periodos introducidos como tuplas."""
        resultado = []
        for fila in range(self.tabla.rowCount()):
            combo = self.tabla.cellWidget(fila, 0)
            trabajador_id = combo.currentData()
            col = 1
            tipo = tipo_por_defecto
            if self.con_tipo:
                tipo = TipoAusencia(self.tabla.cellWidget(fila, col).currentData())
                col += 1
            inicio = self.tabla.cellWidget(fila, col).date().toPython()
            fin = self.tabla.cellWidget(fila, col + 1).date().toPython()
            resultado.append((trabajador_id, tipo, inicio, fin))
        return resultado


class AsistenteCuadrante(QtWidgets.QWizard):
    """Asistente que recaba datos y desencadena la generación."""

    def __init__(self, servicio: ServicioCuadrantes, anio: int, mes: int, parent=None):
        super().__init__(parent)
        self.servicio = servicio
        self.anio = anio
        self.mes = mes
        self.setWindowTitle(
            f"Asistente de generación — {NOMBRES_MES[mes].capitalize()} {anio}")
        self.setWizardStyle(QtWidgets.QWizard.ModernStyle)
        self.resize(760, 560)

        self._pagina_intro()
        self.pagina_vac = self._pagina_periodos(
            "Vacaciones", "¿Hay trabajadores de vacaciones este mes?", con_tipo=False)
        self.pagina_baja = self._pagina_periodos(
            "Bajas médicas", "¿Existe alguna baja médica?", con_tipo=False)
        self.pagina_permiso = self._pagina_periodos(
            "Permisos y formación",
            "Permisos retribuidos, sin sueldo, formación o asuntos propios.", con_tipo=True)
        self._pagina_restricciones()
        self._pagina_incidencias()

    # ------------------------------------------------------------------
    def _pagina_intro(self) -> None:
        pagina = QtWidgets.QWizardPage()
        pagina.setTitle("Generación del cuadrante mensual")
        pagina.setSubTitle(
            f"Se generará el cuadrante de {NOMBRES_MES[self.mes].capitalize()} {self.anio}. "
            "Complete la información de los siguientes pasos.")
        disp = QtWidgets.QVBoxLayout(pagina)
        disp.addWidget(QtWidgets.QLabel(
            "Este asistente recaba toda la información necesaria antes de ejecutar\n"
            "el motor de optimización. Ningún dato es obligatorio salvo que exista."))
        self.addPage(pagina)

    def _pagina_periodos(self, titulo, subtitulo, con_tipo) -> _TablaPeriodos:
        pagina = QtWidgets.QWizardPage()
        pagina.setTitle(titulo)
        pagina.setSubTitle(subtitulo)
        disp = QtWidgets.QVBoxLayout(pagina)
        tabla = _TablaPeriodos(self.servicio, con_tipo=con_tipo)
        disp.addWidget(tabla)
        self.addPage(pagina)
        return tabla

    def _pagina_restricciones(self) -> None:
        pagina = QtWidgets.QWizardPage()
        pagina.setTitle("Restricciones individuales del mes")
        pagina.setSubTitle(
            "Días en los que un trabajador NO puede trabajar o preferencias puntuales.")
        disp = QtWidgets.QVBoxLayout(pagina)
        self.tabla_restr = QtWidgets.QTableWidget(0, 4)
        self.tabla_restr.setHorizontalHeaderLabels(
            ["Trabajador", "Días NO disponibles", "Prefiere noche (días)", "Descripción"])
        self.tabla_restr.horizontalHeader().setStretchLastSection(True)
        disp.addWidget(QtWidgets.QLabel(
            "Introduzca los días separados por comas. Ejemplo: 5, 6, 20."))
        disp.addWidget(self.tabla_restr)
        botones = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("➕ Añadir")
        dele = QtWidgets.QPushButton("🗑️ Quitar")
        add.clicked.connect(self._anadir_restriccion)
        dele.clicked.connect(lambda: self.tabla_restr.removeRow(self.tabla_restr.currentRow()))
        botones.addWidget(add)
        botones.addWidget(dele)
        botones.addStretch()
        disp.addLayout(botones)
        self.addPage(pagina)

    def _anadir_restriccion(self) -> None:
        fila = self.tabla_restr.rowCount()
        self.tabla_restr.insertRow(fila)
        combo = QtWidgets.QComboBox()
        for t in self.servicio.trabajadores.listar(solo_activos=True):
            combo.addItem(t.nombre, t.id)
        self.tabla_restr.setCellWidget(fila, 0, combo)
        for c in (1, 2, 3):
            self.tabla_restr.setItem(fila, c, QtWidgets.QTableWidgetItem(""))

    def _pagina_incidencias(self) -> None:
        pagina = QtWidgets.QWizardPage()
        pagina.setTitle("Incidencias extraordinarias")
        pagina.setSubTitle("Cualquier incidencia extraordinaria del mes (opcional).")
        disp = QtWidgets.QVBoxLayout(pagina)
        self.texto_incidencias = QtWidgets.QPlainTextEdit()
        self.texto_incidencias.setPlaceholderText(
            "Una incidencia por línea. Ejemplo:\n"
            "Refuerzo por evento el día 12.\nAvería del sistema de accesos el fin de semana del 20.")
        disp.addWidget(self.texto_incidencias)
        self.addPage(pagina)

    # ------------------------------------------------------------------
    def guardar_datos(self) -> None:
        """Persiste en la base de datos toda la información recabada."""
        # Vacaciones.
        for tid, _tipo, inicio, fin in self.pagina_vac.recoger(TipoAusencia.VACACIONES):
            self.servicio.ausencias.guardar(
                Ausencia(None, tid, TipoAusencia.VACACIONES, inicio, fin))
        # Bajas.
        for tid, _tipo, inicio, fin in self.pagina_baja.recoger(TipoAusencia.BAJA_MEDICA):
            self.servicio.ausencias.guardar(
                Ausencia(None, tid, TipoAusencia.BAJA_MEDICA, inicio, fin))
        # Permisos / formación.
        for tid, tipo, inicio, fin in self.pagina_permiso.recoger(TipoAusencia.PERMISO_RETRIBUIDO):
            self.servicio.ausencias.guardar(Ausencia(None, tid, tipo, inicio, fin))
        # Restricciones.
        for fila in range(self.tabla_restr.rowCount()):
            combo = self.tabla_restr.cellWidget(fila, 0)
            tid = combo.currentData()
            no_disp = self._parse_dias(self.tabla_restr.item(fila, 1))
            noche = self._parse_dias(self.tabla_restr.item(fila, 2))
            desc = self.tabla_restr.item(fila, 3).text() if self.tabla_restr.item(fila, 3) else ""
            self.servicio.restricciones.guardar(RestriccionTemporal(
                None, tid, self.anio, self.mes,
                dias_no_disponibles=no_disp, dias_prefiere_noche=noche, descripcion=desc))
        # Incidencias.
        for linea in self.texto_incidencias.toPlainText().splitlines():
            if linea.strip():
                self.servicio.incidencias.guardar(
                    Incidencia(None, self.anio, self.mes, linea.strip()))

    @staticmethod
    def _parse_dias(item) -> set[int]:
        if not item or not item.text().strip():
            return set()
        dias = set()
        for parte in item.text().split(","):
            parte = parte.strip()
            if parte.isdigit():
                dias.add(int(parte))
        return dias
