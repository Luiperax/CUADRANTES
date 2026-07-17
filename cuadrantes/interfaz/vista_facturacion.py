"""
Pestaña de FACTURACIÓN: muestra en pantalla el cuadrante de facturación
(agrupado por servicio/OT, con entrada/salida, sumas y totales) y permite
descargarlo en Excel con el mismo formato que se entrega al cliente.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..dominio.calendario import CalendarioMes
from ..exportacion.facturacion import _SERVICIOS, construir_datos_facturacion, rangos_vacaciones

_AZUL = QtGui.QColor("#9DC3E6")
_PEACH = QtGui.QColor("#FCE4D6")
_AMAR = QtGui.QColor("#FFF2CC")
_CYAN = QtGui.QColor("#00B0F0")
_NEGRO = QtGui.QColor("#000000")
_BLANCO = QtGui.QColor("#FFFFFF")
_ROJO = QtGui.QColor("#FF0000")


class VistaFacturacion(QtWidgets.QWidget):
    """Vista del cuadrante de facturación con descarga a Excel."""

    def __init__(self, servicio, parent=None):
        super().__init__(parent)
        self.servicio = servicio
        self.cuadrante = None

        disp = QtWidgets.QVBoxLayout(self)
        barra = QtWidgets.QHBoxLayout()
        self.titulo = QtWidgets.QLabel("Genere o seleccione un cuadrante")
        self.titulo.setObjectName("subtitulo")
        barra.addWidget(self.titulo)
        barra.addStretch()
        self.boton = QtWidgets.QPushButton("📥 Descargar Excel")
        self.boton.setObjectName("primario")
        self.boton.clicked.connect(self._descargar)
        self.boton.setEnabled(False)
        barra.addWidget(self.boton)
        self.boton_pdf = QtWidgets.QPushButton("📄 Descargar PDF")
        self.boton_pdf.clicked.connect(self._descargar_pdf)
        self.boton_pdf.setEnabled(False)
        barra.addWidget(self.boton_pdf)
        disp.addLayout(barra)

        self.tabla = QtWidgets.QTableWidget()
        self.tabla.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.horizontalHeader().setVisible(False)
        fuente = self.tabla.font()
        fuente.setPointSize(8)
        self.tabla.setFont(fuente)
        disp.addWidget(self.tabla)

    # ------------------------------------------------------------------
    def cargar(self, cuadrante) -> None:
        self.cuadrante = cuadrante
        self.boton.setEnabled(cuadrante is not None)
        self.boton_pdf.setEnabled(cuadrante is not None)
        if cuadrante is None:
            self.tabla.clear()
            return
        self._pintar()

    def _item(self, texto="", fondo=None, negrita=False, color=None):
        it = QtWidgets.QTableWidgetItem("" if texto == "" else str(texto))
        it.setTextAlignment(QtCore.Qt.AlignCenter)
        if fondo is not None:
            it.setBackground(fondo)
        if color is not None:
            it.setForeground(color)
        if negrita:
            f = it.font(); f.setBold(True); it.setFont(f)
        return it

    def _pintar(self) -> None:
        cuad = self.cuadrante
        from ..config.constantes import NOMBRES_MES
        self.titulo.setText(
            f"Facturación · {NOMBRES_MES[cuad.mes].capitalize()} {cuad.anio} · "
            "NATURGY · Edificio Avenida de San Luis")
        festivos = self.servicio.festivos_del_mes(cuad.anio, cuad.mes)
        cal = CalendarioMes(cuad.anio, cuad.mes, festivos)
        trab = {t.id: t for t in self.servicio.trabajadores.listar()}
        datos = construir_datos_facturacion(cuad, trab, cal)

        dias = cal.dias
        nd = len(dias)
        col_dia0 = 2
        col_tot = col_dia0 + nd
        col_dif = col_tot + 1
        ncols = col_dif + 1

        vacs = rangos_vacaciones(cuad, trab, cal)
        # Nº de filas: por servicio -> 1 cabecera días + 1 cabecera OT + 3*emp + 1 total.
        filas = 0
        for s in datos["servicios"]:
            filas += 2 + len(s["empleados"]) * 3 + 1
        filas += 1  # total general
        filas += 1 + len(_SERVICIOS)          # pie: título + códigos OT
        if vacs:
            filas += 1 + len(vacs)            # separador + notas de vacaciones
        self.tabla.clear()
        self.tabla.setColumnCount(ncols)
        self.tabla.setRowCount(filas)

        r = 0
        for s in datos["servicios"]:
            r = self._pintar_cabecera_dias(cal, r, col_dia0, col_tot, col_dif)
            # Cabecera negra del servicio.
            self.tabla.setItem(r, 0, self._item(s["codigo"], _NEGRO, True, _ROJO))
            self.tabla.setItem(r, 1, self._item(s["nombre"], _NEGRO, True, _BLANCO))
            for c in range(2, ncols):
                self.tabla.setItem(r, c, self._item("", _NEGRO))
            r += 1
            for emp in s["empleados"]:
                r = self._pintar_empleado(emp, r, col_dia0, col_tot, col_dif)
            # Total diario del servicio.
            self.tabla.setItem(r, 0, self._item(""))
            self.tabla.setItem(r, 1, self._item(""))
            for i, dia in enumerate(dias):
                self.tabla.setItem(r, col_dia0 + i,
                                   self._item(s["totales_dia"][i] or "", _AMAR, True))
            self.tabla.setItem(r, col_tot, self._item(s["total"], _AMAR, True))
            self.tabla.setItem(r, col_dif, self._item(""))
            r += 1

        # Total general.
        self.tabla.setItem(r, 0, self._item("TOTAL GENERAL", _AMAR, True))
        self.tabla.setItem(r, 1, self._item("", _AMAR))
        for i, dia in enumerate(dias):
            self.tabla.setItem(r, col_dia0 + i, self._item(datos["total_general_dia"][i], _AMAR, True))
        self.tabla.setItem(r, col_tot, self._item(datos["total_general"], _AMAR, True))
        self.tabla.setItem(r, col_dif, self._item(""))
        r += 1

        # Pie: leyenda de servicios (OT) y notas de vacaciones.
        def izq(texto, negrita=False, color=None):
            it = self._item(texto, None, negrita, color)
            it.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            return it

        self.tabla.setItem(r, 0, izq("DETALLE DE LOS SERVICIOS (OT)", True))
        self.tabla.setSpan(r, 0, 1, ncols); r += 1
        from ..config.constantes import Puesto  # noqa: F401 (import local ligero)
        for _p, codigo, nombre in _SERVICIOS:
            self.tabla.setItem(r, 0, izq(codigo, True, _ROJO))
            self.tabla.setItem(r, 1, izq(f"esta OT corresponde a {nombre}"))
            self.tabla.setSpan(r, 1, 1, ncols - 1)
            r += 1
        if vacs:
            from ..config.constantes import NOMBRES_MES
            mes_min = NOMBRES_MES[cuad.mes]
            for nombre, ini, fin in vacs:
                self.tabla.setItem(r, 0, izq(
                    f"La VS {nombre} disfruta de vacaciones del {ini} al {fin} "
                    f"de {mes_min}, ambos inclusive."))
                self.tabla.setSpan(r, 0, 1, ncols)
                r += 1

        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, 190)
        self.tabla.setColumnWidth(1, 105)

    def _pintar_cabecera_dias(self, cal, r, col_dia0, col_tot, col_dif) -> int:
        self.tabla.setItem(r, 0, self._item("EMPLEADO", QtGui.QColor("#D9D9D9"), True))
        self.tabla.setItem(r + 1, col_tot, self._item("TOTALES", QtGui.QColor("#D9D9D9"), True))
        for i, dia in enumerate(cal.dias):
            finde = cal.es_fin_de_semana(dia)
            fondo = _AZUL if finde else None
            self.tabla.setItem(r, col_dia0 + i, self._item(cal.letra_dia(dia), fondo, True))
            self.tabla.setItem(r + 1, col_dia0 + i, self._item(dia, fondo, True))
        return r + 2

    def _pintar_empleado(self, emp, r, col_dia0, col_tot, col_dif) -> int:
        f_ent, f_sal, f_sum = r, r + 1, r + 2
        self.tabla.setItem(f_ent, 0, self._item(emp["nombre"], None, True))
        self.tabla.setSpan(f_ent, 0, 3, 1)
        self.tabla.setItem(f_ent, 1, self._item("HORA DE ENTRADA"))
        self.tabla.setItem(f_sal, 1, self._item("HORA DE SALIDA"))
        self.tabla.setItem(f_sum, 1, self._item("SUMA"))
        for i, cel in enumerate(emp["celdas"]):
            base = _AZUL if cel["finde"] else None
            rel_ev = _CYAN if cel["vac"] else base
            self.tabla.setItem(f_ent, col_dia0 + i, self._item(cel["entrada"], rel_ev, True))
            self.tabla.setItem(f_sal, col_dia0 + i, self._item(cel["salida"], rel_ev, True))
            # Fila SUMA siempre coloreada (banda) para diferenciar empleados.
            self.tabla.setItem(f_sum, col_dia0 + i, self._item(cel["suma"], _PEACH))
        self.tabla.setItem(f_ent, col_dif, self._item("HORAS"))
        self.tabla.setItem(f_sal, col_dif, self._item("EXTRAS"))
        self.tabla.setItem(f_sum, col_tot, self._item(emp["total"] or "", _AMAR, True))
        self.tabla.setItem(f_sum, col_dif,
                           self._item(str(int(round(emp["dif"]))), None, True))
        return f_sum + 1

    # ------------------------------------------------------------------
    def _descargar(self) -> None:
        if self.cuadrante is None:
            return
        from ..config.constantes import NOMBRES_MES
        sugerido = f"Facturacion_{NOMBRES_MES[self.cuadrante.mes]}_{self.cuadrante.anio}.xlsx"
        ruta, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Descargar facturación en Excel", sugerido, "Excel (*.xlsx)")
        if ruta:
            self.servicio.exportar_facturacion(self.cuadrante, Path(ruta))
            QtWidgets.QMessageBox.information(
                self, "Facturación", f"Descargado:\n{ruta}")

    def _descargar_pdf(self) -> None:
        if self.cuadrante is None:
            return
        from ..config.constantes import NOMBRES_MES
        sugerido = f"Facturacion_{NOMBRES_MES[self.cuadrante.mes]}_{self.cuadrante.anio}.pdf"
        ruta, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Descargar facturación en PDF", sugerido, "PDF (*.pdf)")
        if ruta:
            self.servicio.exportar_facturacion_pdf(self.cuadrante, Path(ruta))
            QtWidgets.QMessageBox.information(self, "Facturación", f"Descargado:\n{ruta}")
