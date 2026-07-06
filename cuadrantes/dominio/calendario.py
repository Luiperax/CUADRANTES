"""
Utilidades de calendario para la planificación mensual.

Ofrece funciones para determinar los días del mes, identificar fines de semana y
festivos, y agrupar los fines de semana (sábado + domingo) que, según las reglas,
deben ser realizados por el mismo trabajador.
"""

from __future__ import annotations

import calendar
from datetime import date

from ..config.constantes import LETRAS_DIA_SEMANA


class CalendarioMes:
    """Representa el calendario de un mes concreto con sus metadatos."""

    def __init__(self, anio: int, mes: int, festivos: set[date] | None = None):
        self.anio = anio
        self.mes = mes
        self.festivos = festivos or set()
        self.numero_dias = calendar.monthrange(anio, mes)[1]

    @property
    def dias(self) -> list[int]:
        """Lista de números de día (1..n)."""
        return list(range(1, self.numero_dias + 1))

    def fecha(self, dia: int) -> date:
        return date(self.anio, self.mes, dia)

    def dia_semana(self, dia: int) -> int:
        """0 = lunes ... 6 = domingo."""
        return self.fecha(dia).weekday()

    def letra_dia(self, dia: int) -> str:
        return LETRAS_DIA_SEMANA[self.dia_semana(dia)]

    def es_sabado(self, dia: int) -> bool:
        return self.dia_semana(dia) == 5

    def es_domingo(self, dia: int) -> bool:
        return self.dia_semana(dia) == 6

    def es_fin_de_semana(self, dia: int) -> bool:
        return self.dia_semana(dia) >= 5

    def es_festivo(self, dia: int) -> bool:
        return self.fecha(dia) in self.festivos

    def es_festivo_o_finde(self, dia: int) -> bool:
        """Días con cobertura reducida (48 h): sábado, domingo o festivo."""
        return self.es_fin_de_semana(dia) or self.es_festivo(dia)

    def fines_de_semana(self) -> list[tuple[int, int]]:
        """Devuelve la lista de pares (sábado, domingo) completos del mes.

        Solo se consideran fines de semana «completos» aquellos en los que tanto
        el sábado como el domingo caen dentro del mes. Esto permite aplicar la
        regla de que sábado y domingo los realiza el mismo trabajador.
        """
        pares: list[tuple[int, int]] = []
        for dia in self.dias:
            if self.es_sabado(dia) and dia + 1 <= self.numero_dias:
                pares.append((dia, dia + 1))
        return pares

    def sabados(self) -> list[int]:
        return [d for d in self.dias if self.es_sabado(d)]

    def domingos(self) -> list[int]:
        return [d for d in self.dias if self.es_domingo(d)]
