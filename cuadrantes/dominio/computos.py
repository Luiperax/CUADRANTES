"""
Cálculo de cómputos mensuales por trabajador (columnas H.T., H.E., H.N. y más).

Este módulo centraliza la aritmética del cuadrante para que exportadores,
informes y validación utilicen exactamente los mismos números.
"""

from __future__ import annotations

from ..config.constantes import (
    HORAS_NOCTURNAS_POR_NOCHE,
    HORAS_POR_TURNO,
)
from ..datos.modelos import Cuadrante, ResumenTrabajadorMes, Trabajador
from .calendario import CalendarioMes


def calcular_resumenes(
    cuadrante: Cuadrante,
    trabajadores: dict[int, Trabajador],
    calendario: CalendarioMes | None = None,
) -> dict[int, ResumenTrabajadorMes]:
    """Calcula los cómputos de cada trabajador del cuadrante.

    :param cuadrante: cuadrante a analizar.
    :param trabajadores: diccionario ``{id: Trabajador}`` para obtener el
        cómputo mensual personal (necesario para las horas extra).
    :param calendario: calendario del mes (se crea si no se aporta).
    :return: diccionario ``{trabajador_id: ResumenTrabajadorMes}``.
    """
    if calendario is None:
        calendario = CalendarioMes(cuadrante.anio, cuadrante.mes)

    sabados = set(calendario.sabados())
    festivos_reales = {
        d for d in calendario.dias
        if calendario.es_festivo(d) and not calendario.es_fin_de_semana(d)
    }

    resumenes: dict[int, ResumenTrabajadorMes] = {}
    for trabajador_id in cuadrante.trabajadores_ids or trabajadores.keys():
        resumenes[trabajador_id] = ResumenTrabajadorMes(trabajador_id=trabajador_id)

    for (trabajador_id, dia), asignacion in cuadrante.asignaciones.items():
        resumen = resumenes.setdefault(trabajador_id, ResumenTrabajadorMes(trabajador_id))
        if asignacion.es_trabajo:
            resumen.horas_trabajadas += HORAS_POR_TURNO
            resumen.dias_trabajados += 1
            if asignacion.es_noche:
                resumen.numero_noches += 1
                resumen.horas_nocturnas += HORAS_NOCTURNAS_POR_NOCHE
            if dia in sabados and _trabaja_fin_de_semana(cuadrante, trabajador_id, dia):
                resumen.numero_fines_semana += 1
            if dia in festivos_reales:
                resumen.numero_festivos += 1
        elif asignacion.ausencia is not None:
            from ..config.constantes import TipoAusencia

            if asignacion.ausencia is TipoAusencia.VACACIONES:
                resumen.dias_vacaciones += 1
            elif asignacion.ausencia in (None, TipoAusencia.LIBRE):
                resumen.dias_libres += 1
        else:
            resumen.dias_libres += 1

    # Horas extra = horas trabajadas - cómputo mensual personal.
    for trabajador_id, resumen in resumenes.items():
        trabajador = trabajadores.get(trabajador_id)
        computo = trabajador.computo_mensual if trabajador else cuadrante.computo_mensual
        resumen.horas_extra = round(resumen.horas_trabajadas - computo, 1)

    return resumenes


def _trabaja_fin_de_semana(cuadrante: Cuadrante, trabajador_id: int, sabado: int) -> bool:
    """Confirma que la asignación del sábado forma parte de un turno de trabajo."""
    asignacion = cuadrante.obtener(trabajador_id, sabado)
    return bool(asignacion and asignacion.es_trabajo)
