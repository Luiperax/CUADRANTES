"""
Exportación del cuadrante a PDF con ReportLab.

ReportLab permite componer documentos PDF con control preciso de tablas, colores
y estilos, ideal para generar un cuadrante imprimible en A3 apaisado que conserva
la estética del original (rejilla, resaltado de fines de semana y turnos de noche).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepInFrame

from ..config.constantes import NOMBRES_MES, Colores, TipoAusencia
from ..datos.modelos import Cuadrante, Trabajador
from ..dominio.calendario import CalendarioMes
from ..dominio.computos import calcular_resumenes


def _hex(color: str) -> colors.Color:
    return colors.HexColor("#" + color)


class ExportadorPDF:
    """Genera el PDF del cuadrante en A3 apaisado."""

    def __init__(self, cuadrante: Cuadrante, trabajadores: dict[int, Trabajador]):
        self.cuadrante = cuadrante
        self.trabajadores = trabajadores
        self.calendario = CalendarioMes(cuadrante.anio, cuadrante.mes)
        self.resumenes = calcular_resumenes(cuadrante, trabajadores, self.calendario)

    def exportar(self, ruta: str | Path) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        documento = SimpleDocTemplate(
            str(ruta), pagesize=landscape(A3),
            leftMargin=8 * mm, rightMargin=8 * mm, topMargin=8 * mm, bottomMargin=8 * mm,
        )
        tabla = self._construir_tabla()
        # KeepInFrame reescala si la tabla excede el ancho de la página.
        contenido = [
            self._titulo(),
            Spacer(1, 4 * mm),
            KeepInFrame(maxWidth=documento.width, maxHeight=documento.height, content=[tabla], mode="shrink"),
        ]
        documento.build(contenido)
        return ruta

    def _titulo(self) -> Table:
        titulo = (
            f"{self.cuadrante.empresa} — {self.cuadrante.sede}    "
            f"{NOMBRES_MES[self.cuadrante.mes]} {self.cuadrante.anio}    "
            f"C.M.= {self.cuadrante.computo_mensual:.2f}    "
            f"Estado: {self.cuadrante.estado.descripcion}"
        )
        tabla = Table([[titulo]], colWidths=[380 * mm])
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#004080")),
        ]))
        return tabla

    def _construir_tabla(self) -> Table:
        dias = self.calendario.dias
        n_dias = len(dias)

        # --- Filas de encabezado ---
        fila_num = [f"{NOMBRES_MES[self.cuadrante.mes]} {self.cuadrante.anio}"]
        fila_letra = [""]
        for dia in dias:
            fila_num.append(str(dia))
            fila_letra.append(self.calendario.letra_dia(dia))
        fila_num += ["H.T.", "H.E.", "H.N"]
        fila_letra += ["", "", ""]

        datos = [fila_num, fila_letra]
        estilos: list = [
            ("GRID", (0, 0), (-1, -1), 0.4, _hex(Colores.BORDE)),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 5.5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (0, 1), _hex(Colores.CABECERA_MES)),
        ]

        # Resaltado de columnas de fin de semana en las cabeceras.
        for i, dia in enumerate(dias):
            col = i + 1
            if self.calendario.es_festivo_o_finde(dia):
                estilos.append(("BACKGROUND", (col, 0), (col, 1), _hex(Colores.FIN_DE_SEMANA)))

        # --- Filas de trabajadores (dos por trabajador) ---
        fila_actual = 2
        ids = self.cuadrante.trabajadores_ids or list(self.trabajadores.keys())
        for trabajador_id in ids:
            trabajador = self.trabajadores.get(trabajador_id)
            nombre = trabajador.nombre if trabajador else f"Trabajador {trabajador_id}"
            fila_t = [nombre]
            fila_p = [""]
            for i, dia in enumerate(dias):
                col = i + 1
                asignacion = self.cuadrante.obtener(trabajador_id, dia)
                fila_t.append(asignacion.codigo_turno() if asignacion else "")
                fila_p.append(asignacion.codigo_puesto() if asignacion else "")
                # Colores de celda.
                finde = self.calendario.es_festivo_o_finde(dia)
                if asignacion and asignacion.es_cambio_manual:
                    estilos.append(("BACKGROUND", (col, fila_actual), (col, fila_actual), _hex(Colores.CAMBIO)))
                elif asignacion and asignacion.es_noche:
                    estilos.append(("BACKGROUND", (col, fila_actual), (col, fila_actual), _hex(Colores.TURNO_NOCHE)))
                elif asignacion and asignacion.ausencia is TipoAusencia.VACACIONES:
                    estilos.append(("BACKGROUND", (col, fila_actual), (col, fila_actual), _hex(Colores.VACACIONES)))
                elif asignacion and asignacion.ausencia is TipoAusencia.BAJA_MEDICA:
                    estilos.append(("BACKGROUND", (col, fila_actual), (col, fila_actual), _hex(Colores.BAJA)))
                elif finde:
                    estilos.append(("BACKGROUND", (col, fila_actual), (col, fila_actual), _hex(Colores.FIN_DE_SEMANA)))
                if asignacion and asignacion.es_trabajo:
                    estilos.append(("BACKGROUND", (col, fila_actual + 1), (col, fila_actual + 1), _hex(Colores.PUESTO)))
                elif finde:
                    estilos.append(("BACKGROUND", (col, fila_actual + 1), (col, fila_actual + 1), _hex(Colores.FIN_DE_SEMANA)))

            resumen = self.resumenes.get(trabajador_id)
            ht = resumen.horas_trabajadas if resumen else 0
            he = resumen.horas_extra if resumen else 0
            hn = resumen.horas_nocturnas if resumen else 0
            fila_t += [str(ht).replace(".", ","), str(he).replace(".", ","), str(hn).replace(".", ",")]
            fila_p += ["", "", ""]

            datos.append(fila_t)
            datos.append(fila_p)
            # Combinar el nombre y las columnas de cómputo sobre las dos filas.
            estilos.append(("SPAN", (0, fila_actual), (0, fila_actual + 1)))
            estilos.append(("ALIGN", (0, fila_actual), (0, fila_actual + 1), "LEFT"))
            for c in (n_dias + 1, n_dias + 2, n_dias + 3):
                estilos.append(("SPAN", (c, fila_actual), (c, fila_actual + 1)))
            fila_actual += 2

        # --- Fila de cómputo diario ---
        fila_computo = ["COMPUTO HORAS DIARIAS"]
        total = 0
        for dia in dias:
            horas = sum(
                12 for tid in ids
                if (a := self.cuadrante.obtener(tid, dia)) and a.es_trabajo
            )
            total += horas
            fila_computo.append(str(horas))
        fila_computo += [str(total), "", ""]
        datos.append(fila_computo)
        estilos.append(("SPAN", (0, fila_actual), (0, fila_actual)))

        # Anchos de columna.
        ancho_nombre = 42 * mm
        ancho_dia = (380 * mm - ancho_nombre - 3 * 9 * mm) / n_dias
        anchos = [ancho_nombre] + [ancho_dia] * n_dias + [9 * mm, 9 * mm, 9 * mm]

        tabla = Table(datos, colWidths=anchos, repeatCols=1)
        tabla.setStyle(TableStyle(estilos))
        return tabla
