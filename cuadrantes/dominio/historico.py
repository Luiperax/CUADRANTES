"""
Memoria histórica: agregación de cuadrantes anteriores.

Las reglas exigen que el reparto no se base únicamente en el mes actual, sino que
tenga en cuenta la carga acumulada de cada trabajador (horas, noches, fines de
semana, festivos, horas extra...). Este módulo calcula esos acumulados a partir
de los cuadrantes previos para que el motor de optimización pueda compensar a
quien más ha trabajado históricamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config.constantes import HORAS_NOCTURNAS_POR_NOCHE, HORAS_POR_TURNO
from ..datos.modelos import Cuadrante


@dataclass
class CargaHistorica:
    """Acumulados históricos de un trabajador."""

    trabajador_id: int
    horas_totales: float = 0.0
    horas_extra: float = 0.0
    noches: int = 0
    fines_semana: int = 0
    festivos: int = 0
    # Recuento de veces que ha realizado cada puesto (para rotación equilibrada).
    puestos: dict[str, int] = field(default_factory=dict)


class AgregadorHistorico:
    """Calcula la carga histórica acumulada por trabajador."""

    def __init__(
        self,
        cuadrantes_previos: list[Cuadrante],
        festivos_por_mes: dict[tuple[int, int], set[int]] | None = None,
    ):
        """
        :param cuadrantes_previos: cuadrantes de meses anteriores.
        :param festivos_por_mes: días festivos de cada mes ``{(año, mes): {días}}``,
            necesario para contar correctamente quién trabajó los festivos pasados.
        """
        self.cuadrantes = cuadrantes_previos
        self.festivos_por_mes = festivos_por_mes or {}

    def calcular(self) -> dict[int, CargaHistorica]:
        """Devuelve un diccionario ``{trabajador_id: CargaHistorica}``."""
        acumulado: dict[int, CargaHistorica] = {}

        for cuadrante in self.cuadrantes:
            # Detección de fines de semana trabajados: se cuenta un fin de semana
            # por cada sábado en el que el trabajador tuvo asignación de trabajo.
            from .calendario import CalendarioMes

            from datetime import date as _date

            festivos_dias = self.festivos_por_mes.get((cuadrante.anio, cuadrante.mes), set())
            festivos_fechas = {_date(cuadrante.anio, cuadrante.mes, d) for d in festivos_dias}
            calendario = CalendarioMes(cuadrante.anio, cuadrante.mes, festivos_fechas)
            sabados = set(calendario.sabados())

            for (trabajador_id, dia), asignacion in cuadrante.asignaciones.items():
                carga = acumulado.setdefault(trabajador_id, CargaHistorica(trabajador_id))
                if not asignacion.es_trabajo:
                    continue
                carga.horas_totales += HORAS_POR_TURNO
                if asignacion.es_noche:
                    carga.noches += 1
                if dia in sabados:
                    carga.fines_semana += 1
                # Cualquier festivo trabajado cuenta, aunque caiga en fin de semana.
                if dia in festivos_dias:
                    carga.festivos += 1
                puesto = asignacion.codigo_puesto()
                carga.puestos[puesto] = carga.puestos.get(puesto, 0) + 1

            # Horas extra acumuladas respecto al cómputo mensual.
            for trabajador_id in {t for (t, _) in cuadrante.asignaciones}:
                carga = acumulado.setdefault(trabajador_id, CargaHistorica(trabajador_id))
                trabajadas_mes = sum(
                    HORAS_POR_TURNO
                    for (t, _), a in cuadrante.asignaciones.items()
                    if t == trabajador_id and a.es_trabajo
                )
                carga.horas_extra += trabajadas_mes - cuadrante.computo_mensual

        # Cálculo de horas nocturnas (derivado de noches) por comodidad.
        for carga in acumulado.values():
            carga.__dict__.setdefault("horas_nocturnas", carga.noches * HORAS_NOCTURNAS_POR_NOCHE)
        return acumulado

    @staticmethod
    def normalizar_para_equilibrio(
        cargas: dict[int, CargaHistorica], trabajadores_ids: list[int]
    ) -> dict[int, dict[str, float]]:
        """Traduce la carga histórica a «deudas» relativas por trabajador.

        Devuelve, para cada trabajador, cuánto se desvía de la media del grupo en
        horas, noches y fines de semana. Un valor positivo indica que ha trabajado
        MÁS que la media (por tanto conviene aliviarlo el mes siguiente).
        """
        if not trabajadores_ids:
            return {}

        def media(atributo: str) -> float:
            valores = [getattr(cargas.get(t, CargaHistorica(t)), atributo) for t in trabajadores_ids]
            return sum(valores) / len(valores) if valores else 0.0

        media_horas = media("horas_totales")
        media_noches = media("noches")
        media_fines = media("fines_semana")
        media_festivos = media("festivos")

        desvios: dict[int, dict[str, float]] = {}
        for t in trabajadores_ids:
            carga = cargas.get(t, CargaHistorica(t))
            desvios[t] = {
                "horas": carga.horas_totales - media_horas,
                "noches": carga.noches - media_noches,
                "fines_semana": carga.fines_semana - media_fines,
                "festivos": carga.festivos - media_festivos,
            }
        return desvios
