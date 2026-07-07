"""
Modelos de dominio de la aplicación.

Se emplean ``dataclasses`` para representar las entidades del negocio de forma
clara y tipada. Estos objetos son independientes de la base de datos: la capa de
repositorios (``repositorios.py``) se encarga de convertirlos a/desde filas SQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..config.constantes import (
    EstadoCuadrante,
    Puesto,
    TipoAusencia,
    Turno,
)


@dataclass
class Trabajador:
    """Empleado de seguridad privada asignable a los cuadrantes."""

    id: int | None
    nombre: str
    activo: bool = True
    computo_mensual: float = 162.0  # Cómputo mensual personal (puede diferir del general).

    # --- Restricciones individuales (aprendidas de las reglas de negocio) ---
    # Puestos que el trabajador puede realizar en turno diurno (MT).
    puestos_diurnos_permitidos: set[Puesto] = field(
        default_factory=lambda: set(Puesto)
    )
    # Puestos que el trabajador puede realizar en turno de noche (TN).
    puestos_nocturnos_permitidos: set[Puesto] = field(
        default_factory=lambda: {Puesto.F1, Puesto.F2}
    )
    puede_hacer_noches: bool = True

    # Objetivo individual de fines de semana al mes. Si es ``None`` el trabajador
    # se rige por el objetivo general (preferentemente entre uno y dos). Si se fija
    # un número (por ejemplo, 1 para Luis y Fernando), el motor lo trata como un
    # objetivo casi obligatorio (penalización muy alta salvo imposibilidad).
    fines_semana_exactos: int | None = None

    # Jefe de equipo. Los jefes de equipo tienen una reserva especial: el puesto
    # F1 de mañana (MT-F1) en día laborable solo pueden realizarlo ellos. En fin de
    # semana o festivo ese puesto lo puede hacer cualquiera.
    es_jefe_equipo: bool = False
    # Prioridad para el reparto del F1 de mañana entre jefes de equipo. Los días de
    # MT-F1 laborable se reparten a partes iguales entre los jefes; cuando el número
    # no es par, el día de más se asigna al jefe con MAYOR prioridad. (Ej.: Luis con
    # prioridad mayor que Fernando recibe el día extra.)
    prioridad_jefe: int = 0

    # Preferencias (objetivos blandos).
    prefiere_turno_dia: bool = False
    prefiere_turno_noche: bool = False
    notas: str = ""

    def puede_realizar(self, turno: Turno, puesto: Puesto) -> bool:
        """Comprueba si el trabajador está habilitado para un turno-puesto."""
        if turno.es_nocturno:
            if not self.puede_hacer_noches:
                return False
            return puesto in self.puestos_nocturnos_permitidos
        return puesto in self.puestos_diurnos_permitidos


@dataclass
class Ausencia:
    """Periodo de ausencia de un trabajador (vacaciones, baja, permiso...)."""

    id: int | None
    trabajador_id: int
    tipo: TipoAusencia
    fecha_inicio: date
    fecha_fin: date
    descripcion: str = ""

    def cubre(self, dia: date) -> bool:
        return self.fecha_inicio <= dia <= self.fecha_fin


@dataclass
class RestriccionTemporal:
    """Restricción puntual de un trabajador para un mes concreto.

    Ejemplos: «no puede trabajar los días X», «prefiere turno de noche esa
    semana», «limitación temporal por asuntos personales».
    """

    id: int | None
    trabajador_id: int
    anio: int
    mes: int
    # Días del mes en los que NO puede trabajar (1..31).
    dias_no_disponibles: set[int] = field(default_factory=set)
    # Días en los que prefiere turno de día / noche.
    dias_prefiere_dia: set[int] = field(default_factory=set)
    dias_prefiere_noche: set[int] = field(default_factory=set)
    descripcion: str = ""


@dataclass
class Festivo:
    """Día festivo (se cubre como fin de semana: 48 h)."""

    id: int | None
    fecha: date
    descripcion: str = ""


@dataclass
class Incidencia:
    """Incidencia extraordinaria registrada para un mes/cuadrante."""

    id: int | None
    anio: int
    mes: int
    descripcion: str
    trabajador_id: int | None = None
    resuelta: bool = False


@dataclass
class Asignacion:
    """Asignación de un trabajador a un turno-puesto en un día concreto.

    Si ``turno`` y ``puesto`` son ``None`` y hay ``ausencia``, la celda representa
    una ausencia (vacaciones, baja...). Si todo es ``None``, es día libre.
    """

    trabajador_id: int
    dia: int  # Día del mes (1..31).
    turno: Turno | None = None
    puesto: Puesto | None = None
    ausencia: TipoAusencia | None = None
    es_cambio_manual: bool = False  # Marca en magenta en el Excel.

    @property
    def es_trabajo(self) -> bool:
        return self.turno is not None and self.puesto is not None

    @property
    def es_noche(self) -> bool:
        return self.turno is not None and self.turno.es_nocturno

    def codigo_turno(self) -> str:
        """Etiqueta superior de la celda (MT / TN / V / B ...)."""
        if self.es_trabajo:
            return self.turno.value
        if self.ausencia is not None:
            return self.ausencia.value
        return ""

    def codigo_puesto(self) -> str:
        """Etiqueta inferior de la celda (F1 / F2 / MO / EX)."""
        if self.es_trabajo:
            return self.puesto.value
        return ""


@dataclass
class Cuadrante:
    """Cuadrante mensual completo con todas sus asignaciones."""

    id: int | None
    anio: int
    mes: int
    empresa: str
    sede: str
    computo_mensual: float
    estado: EstadoCuadrante = EstadoCuadrante.BORRADOR
    version: int = 1
    fecha_generacion: date | None = None
    # Asignaciones indexadas por (trabajador_id, dia).
    asignaciones: dict[tuple[int, int], Asignacion] = field(default_factory=dict)
    # Trabajadores incluidos en este cuadrante (orden de aparición).
    trabajadores_ids: list[int] = field(default_factory=list)

    def obtener(self, trabajador_id: int, dia: int) -> Asignacion | None:
        return self.asignaciones.get((trabajador_id, dia))

    def establecer(self, asignacion: Asignacion) -> None:
        clave = (asignacion.trabajador_id, asignacion.dia)
        self.asignaciones[clave] = asignacion


@dataclass
class ResumenTrabajadorMes:
    """Cómputos mensuales de un trabajador (columnas H.T./H.E./H.N. y más)."""

    trabajador_id: int
    horas_trabajadas: float = 0.0       # H.T. (solo horas realmente trabajadas).
    horas_extra: float = 0.0            # H.E. (respecto al cómputo efectivo).
    horas_nocturnas: float = 0.0        # H.N.
    numero_noches: int = 0
    numero_fines_semana: int = 0
    numero_festivos: int = 0
    dias_trabajados: int = 0
    dias_vacaciones: int = 0
    dias_libres: int = 0
    # Días de ausencia que computan (vacaciones, permiso retribuido, formación) y
    # las horas de cómputo que aportan (reducen el C.M. exigible).
    dias_ausencia_computable: int = 0
    horas_computo_ausencias: float = 0.0
    # Cómputo mensual efectivo tras descontar las ausencias computables.
    computo_efectivo: float = 0.0
