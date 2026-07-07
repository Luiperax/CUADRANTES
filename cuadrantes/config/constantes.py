"""
Constantes del dominio de planificación de seguridad privada.

Este módulo concentra todo el conocimiento del dominio aprendido a partir de los
cuadrantes reales de NATURGY (sede «AV. SAN LUIS - 77»). Mantener estos valores
centralizados permite que el resto de la aplicación no contenga «números mágicos»
y que cualquier ajuste estructural se realice en un único lugar.

Modelo aprendido del cuadrante original
---------------------------------------
* Cada trabajador ocupa dos filas visuales: la superior indica el TURNO
  (MT = mañana/tarde diurno, TN = turno de noche) y la inferior el PUESTO
  concreto (F1, F2, MO, EX).
* Turnos horarios:
    - MT F1 / MT F2 / MT MO : 07:00 a 19:00 (jornada diurna de 12 h)
    - MT EX                 : 06:00 a 18:00 (jornada diurna de 12 h)
    - TN F1 / TN F2         : 19:00 a 07:00 (jornada nocturna de 12 h)
* Cobertura del servicio:
    - Día laborable  -> 72 h/día = 6 turnos (F1 día, F2 día, MO día, EX día,
      F1 noche, F2 noche).
    - Sábado, domingo y festivo -> 48 h/día = 4 turnos (F1 día, F2 día,
      F1 noche, F2 noche). No se cubren los puestos MO ni EX.
* Cómputo mensual de referencia (C.M.): 162,00 horas.
* Columnas de cierre del cuadrante:
    - H.T. (Horas Trabajadas)      = nº de turnos asignados * 12.
    - H.E. (Horas Extraordinarias) = H.T. - cómputo mensual del trabajador.
    - H.N. (Horas Nocturnas)       = nº de noches * 8 (franja 22:00-06:00).
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Identidad de la empresa / sede (personalizable desde configuración)
# ---------------------------------------------------------------------------
EMPRESA_POR_DEFECTO = "NATURGY"
SEDE_POR_DEFECTO = "AV. SAN LUIS - 77"
LEYENDA_CABECERA = "Cuadrante provisional sujeto a cambios por imponderables del servicio"


# ---------------------------------------------------------------------------
# Duración de las jornadas
# ---------------------------------------------------------------------------
HORAS_POR_TURNO = 12          # Todo turno (diurno o nocturno) dura 12 horas.
HORAS_NOCTURNAS_POR_NOCHE = 8  # Franja nocturna computable (22:00 a 06:00).
COMPUTO_MENSUAL_REFERENCIA = 162.0  # C.M. de referencia en horas.

# Horas de cómputo que aporta cada día de ausencia computable (vacaciones,
# permiso retribuido, formación). Valor obtenido por ingeniería inversa de los
# cuadrantes reales de NATURGY: la columna «cómputos personales» reduce el C.M. en
# exactamente 5,34 h por cada día de vacaciones/permiso (verificado en múltiples
# trabajadores y meses). Es decir, un día de vacaciones «cuenta» como 5,34 h a
# efectos de horas, en lugar de como 0. La baja médica NO computa (déficit total).
HORAS_COMPUTO_POR_DIA_AUSENCIA = 5.34


class Turno(str, Enum):
    """Franja horaria de un turno de trabajo."""

    MANANA_TARDE = "MT"   # Jornada diurna.
    NOCHE = "TN"          # Jornada nocturna.

    @property
    def es_nocturno(self) -> bool:
        return self is Turno.NOCHE

    @property
    def descripcion(self) -> str:
        return {
            Turno.MANANA_TARDE: "Mañana/Tarde (diurno)",
            Turno.NOCHE: "Noche (nocturno)",
        }[self]


class Puesto(str, Enum):
    """Puesto físico que debe cubrirse en el servicio."""

    F1 = "F1"
    F2 = "F2"
    MO = "MO"
    EX = "EX"

    @property
    def descripcion(self) -> str:
        return {
            Puesto.F1: "Puesto fijo 1",
            Puesto.F2: "Puesto fijo 2",
            Puesto.MO: "Puesto MO (apoyo diurno)",
            Puesto.EX: "Puesto EX (extra diurno 06:00-18:00)",
        }[self]


class TipoAusencia(str, Enum):
    """Códigos de ausencia que pueden aparecer en una celda del cuadrante."""

    VACACIONES = "V"
    BAJA_MEDICA = "B"
    PERMISO_RETRIBUIDO = "PR"
    PERMISO_SIN_SUELDO = "PS"
    FORMACION = "FO"
    ASUNTOS_PROPIOS = "AP"
    LIBRE = "L"           # Día de descanso ordinario (celda vacía en el original).

    @property
    def descripcion(self) -> str:
        return {
            TipoAusencia.VACACIONES: "Vacaciones",
            TipoAusencia.BAJA_MEDICA: "Baja médica",
            TipoAusencia.PERMISO_RETRIBUIDO: "Permiso retribuido",
            TipoAusencia.PERMISO_SIN_SUELDO: "Permiso sin sueldo",
            TipoAusencia.FORMACION: "Formación",
            TipoAusencia.ASUNTOS_PROPIOS: "Asuntos propios",
            TipoAusencia.LIBRE: "Día libre (a petición)",
        }[self]

    @property
    def cuenta_como_trabajada(self) -> bool:
        """Indica si la ausencia computa como jornada trabajada a efectos de horas."""
        # Vacaciones, permisos retribuidos, formación y baja pueden computar en el
        # cálculo del cómputo mensual del trabajador, pero NO como turno cubierto.
        return self in {
            TipoAusencia.VACACIONES,
            TipoAusencia.PERMISO_RETRIBUIDO,
            TipoAusencia.FORMACION,
        }


# ---------------------------------------------------------------------------
# Definición de un «turno-puesto» concreto (la unidad mínima a asignar)
# ---------------------------------------------------------------------------
class FranjaHoraria:
    """Descripción del horario de un turno-puesto para informes y exportación."""

    def __init__(self, inicio: str, fin: str):
        self.inicio = inicio
        self.fin = fin

    def __str__(self) -> str:  # pragma: no cover - representación trivial
        return f"{self.inicio} A {self.fin}"


# Horario textual exacto tal y como aparece en la leyenda del cuadrante original.
HORARIOS = {
    (Turno.MANANA_TARDE, Puesto.F1): FranjaHoraria("7:00", "19:00"),
    (Turno.MANANA_TARDE, Puesto.F2): FranjaHoraria("7:00", "19:00"),
    (Turno.MANANA_TARDE, Puesto.MO): FranjaHoraria("7:00", "19:00"),
    (Turno.MANANA_TARDE, Puesto.EX): FranjaHoraria("6:00", "18:00"),
    (Turno.NOCHE, Puesto.F1): FranjaHoraria("19:00", "7:00"),
    (Turno.NOCHE, Puesto.F2): FranjaHoraria("19:00", "7:00"),
}


# Combinaciones válidas de turno + puesto según la operativa del servicio.
PUESTOS_DIURNOS_LABORABLE = (Puesto.F1, Puesto.F2, Puesto.MO, Puesto.EX)
PUESTOS_NOCTURNOS = (Puesto.F1, Puesto.F2)
PUESTOS_DIURNOS_FESTIVO = (Puesto.F1, Puesto.F2)


def turnos_puesto_requeridos(es_festivo_o_finde: bool) -> list[tuple[Turno, Puesto]]:
    """Devuelve la lista de turno-puesto que deben cubrirse en un día concreto.

    :param es_festivo_o_finde: ``True`` si el día es sábado, domingo o festivo.
    :return: lista de tuplas ``(Turno, Puesto)`` obligatorias ese día.
    """
    if es_festivo_o_finde:
        diurnos = PUESTOS_DIURNOS_FESTIVO
    else:
        diurnos = PUESTOS_DIURNOS_LABORABLE

    requeridos: list[tuple[Turno, Puesto]] = [(Turno.MANANA_TARDE, p) for p in diurnos]
    requeridos += [(Turno.NOCHE, p) for p in PUESTOS_NOCTURNOS]
    return requeridos


# ---------------------------------------------------------------------------
# Letras de los días de la semana en castellano (como en el cuadrante original)
# ---------------------------------------------------------------------------
# 0 = lunes ... 6 = domingo (compatible con datetime.weekday()).
LETRAS_DIA_SEMANA = ["L", "M", "X", "J", "V", "S", "D"]
NOMBRES_MES = [
    "", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]


# ---------------------------------------------------------------------------
# Estados posibles de un cuadrante
# ---------------------------------------------------------------------------
class EstadoCuadrante(str, Enum):
    BORRADOR = "BORRADOR"
    GENERADO_CON_INCIDENCIAS = "GENERADO_CON_INCIDENCIAS"
    VALIDADO = "VALIDADO"

    @property
    def descripcion(self) -> str:
        return {
            EstadoCuadrante.BORRADOR: "Borrador",
            EstadoCuadrante.GENERADO_CON_INCIDENCIAS: "Generado con incidencias justificadas",
            EstadoCuadrante.VALIDADO: "Validado",
        }[self]


# ---------------------------------------------------------------------------
# Paleta de colores aprendida del cuadrante original (formato hexadecimal ARGB
# para OpenPyXL, sin el prefijo «#»). Se usan también en la interfaz.
# ---------------------------------------------------------------------------
class Colores:
    CABECERA_MES = "92D050"       # Verde de la celda del nombre del mes.
    FIN_DE_SEMANA = "FFFF00"      # Amarillo de las columnas de sábado/domingo.
    TURNO_NOCHE = "00B0F0"        # Cian de las etiquetas de turno de noche.
    PUESTO = "00FF99"             # Verde agua de las etiquetas de puesto.
    CAMBIO = "FF00FF"             # Magenta que marca celdas modificadas.
    VACACIONES = "FFC000"         # Naranja para vacaciones.
    BAJA = "FF0000"               # Rojo para bajas.
    BORDE = "000000"              # Negro de los bordes.
    BLANCO = "FFFFFF"
    TEXTO = "000000"
