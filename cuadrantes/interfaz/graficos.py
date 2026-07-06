"""
Componentes gráficos ligeros dibujados con QPainter.

Se implementa un gráfico de barras propio para no depender de módulos adicionales
(QtCharts), manteniendo la aplicación ligera y con el aspecto del tema oscuro.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .tema import PaletaOscura


class GraficoBarras(QtWidgets.QWidget):
    """Gráfico de barras horizontal sencillo (etiqueta + valor)."""

    def __init__(self, titulo: str = "", parent=None):
        super().__init__(parent)
        self.titulo = titulo
        self.datos: list[tuple[str, float]] = []
        self.color = PaletaOscura.ACENTO
        self.setMinimumHeight(180)

    def establecer_datos(self, datos: list[tuple[str, float]], color: str | None = None) -> None:
        self.datos = datos
        if color:
            self.color = color
        self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.Antialiasing)
        ancho = self.width()
        alto = self.height()

        pintor.setPen(QtGui.QColor(PaletaOscura.TEXTO))
        fuente = pintor.font()
        fuente.setBold(True)
        pintor.setFont(fuente)
        if self.titulo:
            pintor.drawText(10, 18, self.titulo)

        if not self.datos:
            pintor.setPen(QtGui.QColor(PaletaOscura.TEXTO_TENUE))
            pintor.drawText(10, 40, "Sin datos")
            return

        maximo = max((v for _, v in self.datos), default=1) or 1
        margen_izq = 160
        y = 34
        altura_barra = min(22, (alto - 40) // max(1, len(self.datos)))
        fuente.setBold(False)
        pintor.setFont(fuente)

        for etiqueta, valor in self.datos:
            pintor.setPen(QtGui.QColor(PaletaOscura.TEXTO_TENUE))
            pintor.drawText(10, y + altura_barra - 6, etiqueta[:22])
            ancho_barra = int((ancho - margen_izq - 60) * (valor / maximo))
            rect = QtCore.QRect(margen_izq, y, max(1, ancho_barra), altura_barra - 4)
            pintor.fillRect(rect, QtGui.QColor(self.color))
            pintor.setPen(QtGui.QColor(PaletaOscura.TEXTO))
            pintor.drawText(margen_izq + ancho_barra + 6, y + altura_barra - 6, f"{valor:g}")
            y += altura_barra
