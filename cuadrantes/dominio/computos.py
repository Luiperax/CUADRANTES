"""
Cálculo de cómputos mensuales por trabajador (columnas H.T., H.E., H.N. y más).

Este módulo centraliza la aritmética del cuadrante para que exportadores,
informes y validación utilicen exactamente los mismos números.
"""

from __future__ import annotations

from ..config.constantes import (
    HORAS_COMPUTO_POR_DIA_AUSENCIA,
    HORAS_NOCTURNAS_POR_NOCHE,
    HORAS_POR_TURNO,
)
from ..datos.modelos import Cuadrante, ResumenTrabajadorMes, Trabajador
from .calendario import CalendarioMes


def calcular_resumenes(
    cuadrante: Cuadrante,
    trabajadores: dict[int, Trabajador],
    calendario: CalendarioMes | None = None,
    horas_computo_por_dia_ausencia: float = HORAS_COMPUTO_POR_DIA_AUSENCIA,
) -> dict[int, ResumenTrabajadorMes]:
    """Calcula los cómputos de cada trabajador del cuadrante.

    :param cuadrante: cuadrante a analizar.
    :param trabajadores: diccionario ``{id: Trabajador}`` para obtener el
        cómputo mensual personal (necesario para las horas extra).
    :param calendario: calendario del mes (se crea si no se aporta).
    :param horas_computo_por_dia_ausencia: horas que aporta cada día de ausencia
        computable (vacaciones, permiso retribuido, formación). Reduce el cómputo
        mensual exigible, igual que en los cuadrantes reales de NATURGY.
    :return: diccionario ``{trabajador_id: ResumenTrabajadorMes}``.
    """
    if calendario is None:
        calendario = CalendarioMes(cuadrante.anio, cuadrante.mes)

    sabados = set(calendario.sabados())
    # Se cuenta como festivo trabajado CUALQUIER día festivo, aunque caiga en
    # sábado o domingo. Un festivo trabajado en fin de semana cuenta a la vez como
    # fin de semana y como festivo (son dos magnitudes distintas).
    festivos_reales = {d for d in calendario.dias if calendario.es_festivo(d)}

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
            if asignacion.ausencia is TipoAusencia.LIBRE:
                resumen.dias_libres += 1
            # Vacaciones, permiso retribuido y formación aportan horas de cómputo.
            if asignacion.ausencia.cuenta_como_trabajada:
                resumen.dias_ausencia_computable += 1
                resumen.horas_computo_ausencias += horas_computo_por_dia_ausencia
        else:
            resumen.dias_libres += 1

    # El cómputo mensual exigible se reduce con las ausencias computables (cada
    # día de vacaciones/permiso «cuenta» como horas). Las horas extra (H.E.) se
    # calculan respecto a ese cómputo efectivo, igual que en el cuadrante original.
    for trabajador_id, resumen in resumenes.items():
        trabajador = trabajadores.get(trabajador_id)
        computo = trabajador.computo_mensual if trabajador else cuadrante.computo_mensual
        resumen.computo_efectivo = round(computo - resumen.horas_computo_ausencias, 2)
        resumen.horas_extra = round(resumen.horas_trabajadas - resumen.computo_efectivo, 1)

    return resumenes


def _trabaja_fin_de_semana(cuadrante: Cuadrante, trabajador_id: int, sabado: int) -> bool:
    """Confirma que la asignación del sábado forma parte de un turno de trabajo."""
    asignacion = cuadrante.obtener(trabajador_id, sabado)
    return bool(asignacion and asignacion.es_trabajo)
