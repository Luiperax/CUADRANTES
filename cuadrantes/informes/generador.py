"""
Generación de informes y estadísticas del cuadrante.

Produce los informes exigidos por el pliego:

* Informe de horas (ordinarias).
* Informe de horas extraordinarias.
* Informe de noches.
* Informe de fines de semana.
* Informe de vacaciones.
* Informe de equilibrio.
* Informe de incidencias.
* Informe de validación (auditoría).

Cada informe se modela como una tabla (cabeceras + filas) neutra respecto al
formato, de modo que puede volcarse a texto, a la interfaz gráfica o a PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config.configuracion import Configuracion
from ..datos.modelos import Ausencia, Cuadrante, Incidencia, Trabajador
from ..dominio.calendario import CalendarioMes
from ..dominio.computos import calcular_resumenes
from ..validacion.auditoria import Auditor


@dataclass
class Informe:
    """Representación tabular de un informe."""

    titulo: str
    cabeceras: list[str]
    filas: list[list[str]] = field(default_factory=list)
    resumen: str = ""

    def a_texto(self) -> str:
        """Vuelca el informe a texto monoespaciado alineado."""
        anchos = [len(c) for c in self.cabeceras]
        for fila in self.filas:
            for i, celda in enumerate(fila):
                anchos[i] = max(anchos[i], len(str(celda)))
        lineas = [self.titulo, "=" * len(self.titulo)]
        cab = "  ".join(str(c).ljust(anchos[i]) for i, c in enumerate(self.cabeceras))
        lineas.append(cab)
        lineas.append("-" * len(cab))
        for fila in self.filas:
            lineas.append("  ".join(str(c).ljust(anchos[i]) for i, c in enumerate(fila)))
        if self.resumen:
            lineas.append("")
            lineas.append(self.resumen)
        return "\n".join(lineas)


class GeneradorInformes:
    """Construye todos los informes de un cuadrante."""

    def __init__(
        self,
        cuadrante: Cuadrante,
        trabajadores: dict[int, Trabajador],
        configuracion: Configuracion,
        ausencias: list[Ausencia] | None = None,
        incidencias: list[Incidencia] | None = None,
    ):
        self.cuadrante = cuadrante
        self.trabajadores = trabajadores
        self.config = configuracion
        self.ausencias = ausencias or []
        self.incidencias = incidencias or []
        self.calendario = CalendarioMes(cuadrante.anio, cuadrante.mes)
        self.resumenes = calcular_resumenes(cuadrante, trabajadores, self.calendario)

    def _nombre(self, tid: int) -> str:
        t = self.trabajadores.get(tid)
        return t.nombre if t else f"Trabajador {tid}"

    def _ids(self) -> list[int]:
        return self.cuadrante.trabajadores_ids or list(self.trabajadores.keys())

    # ------------------------------------------------------------------
    def informe_horas(self) -> Informe:
        filas = []
        total = 0.0
        for tid in self._ids():
            r = self.resumenes.get(tid)
            if not r:
                continue
            total += r.horas_trabajadas
            filas.append([self._nombre(tid), f"{r.horas_trabajadas:.0f}", str(r.dias_trabajados)])
        return Informe(
            "Informe de horas ordinarias", ["Trabajador", "Horas (H.T.)", "Días trabajados"], filas,
            resumen=f"Total de horas del servicio: {total:.0f} h",
        )

    def informe_horas_extra(self) -> Informe:
        filas = []
        for tid in self._ids():
            r = self.resumenes.get(tid)
            if not r:
                continue
            filas.append([self._nombre(tid), f"{r.horas_extra:+.1f}"])
        extras = [self.resumenes[tid].horas_extra for tid in self._ids() if tid in self.resumenes]
        rango = (max(extras) - min(extras)) if extras else 0
        return Informe(
            "Informe de horas extraordinarias", ["Trabajador", "Horas extra (H.E.)"], filas,
            resumen=f"Diferencia máx-mín de horas extra: {rango:.1f} h",
        )

    def informe_noches(self) -> Informe:
        filas = []
        for tid in self._ids():
            r = self.resumenes.get(tid)
            if not r:
                continue
            filas.append([self._nombre(tid), str(r.numero_noches), f"{r.horas_nocturnas:.0f}"])
        return Informe(
            "Informe de noches", ["Trabajador", "Nº noches", "Horas nocturnas (H.N.)"], filas,
        )

    def informe_fines_semana(self) -> Informe:
        filas = []
        for tid in self._ids():
            r = self.resumenes.get(tid)
            if not r:
                continue
            filas.append([self._nombre(tid), str(r.numero_fines_semana), str(r.numero_festivos)])
        return Informe(
            "Informe de fines de semana y festivos",
            ["Trabajador", "Fines de semana", "Festivos"], filas,
        )

    def informe_vacaciones(self) -> Informe:
        from ..config.constantes import TipoAusencia

        filas = []
        for ausencia in self.ausencias:
            if ausencia.tipo is TipoAusencia.VACACIONES:
                filas.append([
                    self._nombre(ausencia.trabajador_id),
                    ausencia.fecha_inicio.strftime("%d/%m/%Y"),
                    ausencia.fecha_fin.strftime("%d/%m/%Y"),
                    str((ausencia.fecha_fin - ausencia.fecha_inicio).days + 1),
                ])
        return Informe(
            "Informe de vacaciones", ["Trabajador", "Inicio", "Fin", "Días"], filas,
        )

    def informe_equilibrio(self) -> Informe:
        filas = []
        for tid in self._ids():
            r = self.resumenes.get(tid)
            if not r:
                continue
            filas.append([
                self._nombre(tid), f"{r.horas_trabajadas:.0f}", f"{r.horas_extra:+.1f}",
                str(r.numero_noches), str(r.numero_fines_semana),
            ])
        return Informe(
            "Informe de equilibrio general",
            ["Trabajador", "H.T.", "H.E.", "Noches", "Findes"], filas,
            resumen="Objetivo: minimizar las diferencias entre trabajadores en todas las columnas.",
        )

    def informe_incidencias(self) -> Informe:
        filas = []
        for inc in self.incidencias:
            filas.append([
                self._nombre(inc.trabajador_id) if inc.trabajador_id else "General",
                inc.descripcion,
                "Sí" if inc.resuelta else "No",
            ])
        return Informe(
            "Informe de incidencias", ["Afectado", "Descripción", "Resuelta"], filas,
        )

    def informe_validacion(self) -> Informe:
        auditor = Auditor(self.cuadrante, self.trabajadores, self.config, self.ausencias)
        informe_aud = auditor.auditar()
        filas = []
        for regla in informe_aud.reglas:
            filas.append([
                regla.nombre, regla.estado.value, regla.motivo[:60],
                regla.solucion_propuesta[:60] if regla.solucion_propuesta else "-",
            ])
        return Informe(
            "Informe de validación (auditoría)",
            ["Regla", "Estado", "Motivo", "Solución propuesta"], filas,
            resumen=f"Estado del cuadrante: {informe_aud.estado_cuadrante.descripcion}",
        )

    # ------------------------------------------------------------------
    def todos(self) -> list[Informe]:
        return [
            self.informe_horas(),
            self.informe_horas_extra(),
            self.informe_noches(),
            self.informe_fines_semana(),
            self.informe_vacaciones(),
            self.informe_equilibrio(),
            self.informe_incidencias(),
            self.informe_validacion(),
        ]

    def exportar_pdf(self, ruta: str | Path) -> Path:
        """Vuelca todos los informes a un único PDF."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(ruta), pagesize=A4,
                                leftMargin=15 * mm, rightMargin=15 * mm,
                                topMargin=15 * mm, bottomMargin=15 * mm)
        estilos = getSampleStyleSheet()
        elementos = [
            Paragraph(
                f"Informes del cuadrante — {self.cuadrante.empresa} {self.cuadrante.sede} "
                f"({self.cuadrante.mes:02d}/{self.cuadrante.anio})", estilos["Title"]),
            Spacer(1, 6 * mm),
        ]
        for informe in self.todos():
            elementos.append(Paragraph(informe.titulo, estilos["Heading2"]))
            datos = [informe.cabeceras] + (informe.filas or [["(sin datos)"] + [""] * (len(informe.cabeceras) - 1)])
            tabla = Table(datos, repeatRows=1)
            tabla.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004080")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))
            elementos.append(tabla)
            if informe.resumen:
                elementos.append(Paragraph(informe.resumen, estilos["Italic"]))
            elementos.append(Spacer(1, 5 * mm))
        doc.build(elementos)
        return ruta
