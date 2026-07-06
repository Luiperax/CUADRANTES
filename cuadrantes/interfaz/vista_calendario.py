"""
Vista de calendario mensual del cuadrante.

Muestra el cuadrante con el mismo esquema de dos filas por trabajador (turno y
puesto), resaltando fines de semana, noches y cambios manuales. Permite la
edición manual de cada celda con recálculo y revalidación automáticos tras cada
cambio.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..config.constantes import Puesto, TipoAusencia, Turno
from ..datos.modelos import Asignacion, Cuadrante, Trabajador
from ..dominio.calendario import CalendarioMes
from ..dominio.computos import calcular_resumenes
from .tema import PaletaOscura


class DialogoEdicionCelda(QtWidgets.QDialog):
    """Diálogo para editar la asignación de un trabajador en un día."""

    def __init__(self, trabajador: Trabajador, asignacion: Asignacion | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar asignación")
        self.trabajador = trabajador
        disp = QtWidgets.QFormLayout(self)

        self.combo_estado = QtWidgets.QComboBox()
        self.combo_estado.addItems(["Trabaja", "Libre", "Vacaciones", "Baja médica", "Permiso"])
        self.combo_turno = QtWidgets.QComboBox()
        for turno in Turno:
            self.combo_turno.addItem(turno.descripcion, turno.value)
        self.combo_puesto = QtWidgets.QComboBox()
        for puesto in Puesto:
            self.combo_puesto.addItem(f"{puesto.value} — {puesto.descripcion}", puesto.value)

        disp.addRow("Estado:", self.combo_estado)
        disp.addRow("Turno:", self.combo_turno)
        disp.addRow("Puesto:", self.combo_puesto)

        # Estado inicial.
        if asignacion and asignacion.es_trabajo:
            self.combo_estado.setCurrentText("Trabaja")
            self.combo_turno.setCurrentText(asignacion.turno.descripcion)
            idx = self.combo_puesto.findData(asignacion.puesto.value)
            self.combo_puesto.setCurrentIndex(max(0, idx))
        elif asignacion and asignacion.ausencia is TipoAusencia.VACACIONES:
            self.combo_estado.setCurrentText("Vacaciones")
        else:
            self.combo_estado.setCurrentText("Libre")

        self.combo_estado.currentTextChanged.connect(self._actualizar_visibilidad)
        self._actualizar_visibilidad()

        botones = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        disp.addRow(botones)

    def _actualizar_visibilidad(self) -> None:
        trabaja = self.combo_estado.currentText() == "Trabaja"
        self.combo_turno.setEnabled(trabaja)
        self.combo_puesto.setEnabled(trabaja)

    def asignacion_resultante(self, dia: int) -> Asignacion:
        estado = self.combo_estado.currentText()
        if estado == "Trabaja":
            turno = Turno(self.combo_turno.currentData())
            puesto = Puesto(self.combo_puesto.currentData())
            return Asignacion(self.trabajador.id, dia, turno=turno, puesto=puesto,
                              es_cambio_manual=True)
        mapa = {
            "Vacaciones": TipoAusencia.VACACIONES,
            "Baja médica": TipoAusencia.BAJA_MEDICA,
            "Permiso": TipoAusencia.PERMISO_RETRIBUIDO,
            "Libre": TipoAusencia.LIBRE,
        }
        return Asignacion(self.trabajador.id, dia, ausencia=mapa.get(estado),
                          es_cambio_manual=True)


class VistaCalendario(QtWidgets.QWidget):
    """Rejilla mensual del cuadrante con edición manual."""

    cuadrante_modificado = QtCore.Signal()

    def __init__(self, trabajadores: dict[int, Trabajador], parent=None):
        super().__init__(parent)
        self.trabajadores = trabajadores
        self.cuadrante: Cuadrante | None = None
        self.calendario: CalendarioMes | None = None
        self.filtro_texto = ""

        disp = QtWidgets.QVBoxLayout(self)
        self.tabla = QtWidgets.QTableWidget()
        self.tabla.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tabla.cellDoubleClicked.connect(self._editar_celda)
        self.tabla.verticalHeader().setVisible(False)
        disp.addWidget(self.tabla)

    # ------------------------------------------------------------------
    def cargar(self, cuadrante: Cuadrante) -> None:
        self.cuadrante = cuadrante
        self.calendario = CalendarioMes(cuadrante.anio, cuadrante.mes)
        self._pintar()

    def aplicar_filtro(self, texto: str) -> None:
        self.filtro_texto = texto.lower().strip()
        self._pintar()

    def _ids_visibles(self) -> list[int]:
        ids = self.cuadrante.trabajadores_ids or list(self.trabajadores.keys())
        if not self.filtro_texto:
            return ids
        return [
            tid for tid in ids
            if self.filtro_texto in self.trabajadores.get(tid).nombre.lower()
        ] if self.trabajadores else ids

    def _pintar(self) -> None:
        if not self.cuadrante:
            return
        cal = self.calendario
        n_dias = cal.numero_dias
        ids = self._ids_visibles()

        # Columnas: nombre + días + H.T./H.E./H.N.
        self.tabla.clear()
        self.tabla.setColumnCount(1 + n_dias + 3)
        self.tabla.setRowCount(len(ids) * 2 + 1)  # 2 por trabajador + cómputo diario.

        cabeceras = ["Trabajador"] + [f"{d}\n{cal.letra_dia(d)}" for d in cal.dias] + ["H.T.", "H.E.", "H.N"]
        self.tabla.setHorizontalHeaderLabels(cabeceras)
        self.tabla.horizontalHeader().setDefaultSectionSize(30)
        self.tabla.setColumnWidth(0, 200)

        resumenes = calcular_resumenes(self.cuadrante, self.trabajadores, cal)

        for i, tid in enumerate(ids):
            fila_t = i * 2
            fila_p = fila_t + 1
            nombre = self.trabajadores.get(tid).nombre if self.trabajadores.get(tid) else str(tid)
            item_nombre = QtWidgets.QTableWidgetItem(nombre)
            item_nombre.setData(QtCore.Qt.UserRole, tid)
            self.tabla.setItem(fila_t, 0, item_nombre)
            self.tabla.setSpan(fila_t, 0, 2, 1)

            for dia in cal.dias:
                col = dia
                asig = self.cuadrante.obtener(tid, dia)
                finde = cal.es_festivo_o_finde(dia)
                self._pintar_celda(fila_t, col, asig.codigo_turno() if asig else "", asig, finde, es_turno=True)
                self._pintar_celda(fila_p, col, asig.codigo_puesto() if asig else "", asig, finde, es_turno=False)

            resumen = resumenes.get(tid)
            col_ht = 1 + n_dias
            for offset, valor in enumerate((
                resumen.horas_trabajadas if resumen else 0,
                f"{resumen.horas_extra:+.0f}" if resumen else 0,
                resumen.horas_nocturnas if resumen else 0,
            )):
                item = QtWidgets.QTableWidgetItem(str(valor))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setFont(QtGui.QFont("", -1, QtGui.QFont.Bold))
                self.tabla.setItem(fila_t, col_ht + offset, item)
                self.tabla.setSpan(fila_t, col_ht + offset, 2, 1)

        # Fila de cómputo diario.
        fila_computo = len(ids) * 2
        item = QtWidgets.QTableWidgetItem("CÓMPUTO HORAS DIARIAS")
        item.setFont(QtGui.QFont("", -1, QtGui.QFont.Bold))
        self.tabla.setItem(fila_computo, 0, item)
        for dia in cal.dias:
            horas = sum(
                12 for tid in ids
                if (a := self.cuadrante.obtener(tid, dia)) and a.es_trabajo
            )
            celda = QtWidgets.QTableWidgetItem(str(horas))
            celda.setTextAlignment(QtCore.Qt.AlignCenter)
            self.tabla.setItem(fila_computo, dia, celda)

        self.tabla.resizeRowsToContents()

    def _pintar_celda(self, fila, col, texto, asig, finde, es_turno) -> None:
        item = QtWidgets.QTableWidgetItem(texto)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        color = None
        if asig and asig.es_cambio_manual and es_turno:
            color = PaletaOscura.ERROR
        elif es_turno and asig and asig.es_noche:
            color = PaletaOscura.NOCHE
        elif es_turno and asig and asig.ausencia is TipoAusencia.VACACIONES:
            color = PaletaOscura.VACACIONES
        elif not es_turno and asig and asig.es_trabajo:
            color = PaletaOscura.EXITO
        elif finde:
            color = PaletaOscura.FIN_SEMANA
        if color:
            item.setBackground(QtGui.QColor(color))
            if color in (PaletaOscura.NOCHE, PaletaOscura.EXITO, PaletaOscura.ERROR):
                item.setForeground(QtGui.QColor("#0d0d0d"))
        self.tabla.setItem(fila, col, item)

    # ------------------------------------------------------------------
    def _editar_celda(self, fila, columna) -> None:
        if not self.cuadrante or columna == 0 or columna > self.calendario.numero_dias:
            return
        ids = self._ids_visibles()
        indice = fila // 2
        if indice >= len(ids):
            return
        tid = ids[indice]
        dia = columna
        trabajador = self.trabajadores.get(tid)
        asig = self.cuadrante.obtener(tid, dia)
        dialogo = DialogoEdicionCelda(trabajador, asig, self)
        if dialogo.exec() == QtWidgets.QDialog.Accepted:
            nueva = dialogo.asignacion_resultante(dia)
            self.cuadrante.establecer(nueva)
            self._pintar()
            self.cuadrante_modificado.emit()
