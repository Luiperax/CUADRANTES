"""
Datos iniciales y equipo actual del centro (AV. SAN LUIS 77).

Define el **equipo actual** del centro con sus restricciones individuales y ofrece
dos operaciones:

* :func:`cargar_plantilla_ejemplo` — carga el equipo si la base de datos está vacía.
* :func:`sincronizar_equipo` — reconcilia la plantilla existente con el equipo
  actual: da de alta a quien falte, reactiva y actualiza restricciones, y
  **desactiva** (sin borrar) a quien ya no forma parte del equipo, preservando así
  todo el histórico de cuadrantes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config.constantes import Puesto
from ..datos.modelos import Trabajador
from ..servicio import ServicioCuadrantes

_TODOS = set(Puesto)


@dataclass
class _PlantillaTrabajador:
    """Definición declarativa de un trabajador del equipo actual."""

    nombre: str
    puestos_diurnos: set = field(default_factory=lambda: set(_TODOS))
    puestos_nocturnos: set = field(default_factory=lambda: {Puesto.F1, Puesto.F2})
    puede_hacer_noches: bool = True
    fines_semana_exactos: int | None = None
    es_jefe_equipo: bool = False
    prioridad_jefe: int = 0
    notas: str = ""

    def a_trabajador(self) -> Trabajador:
        return Trabajador(
            id=None, nombre=self.nombre,
            puestos_diurnos_permitidos=set(self.puestos_diurnos),
            puestos_nocturnos_permitidos=set(self.puestos_nocturnos),
            puede_hacer_noches=self.puede_hacer_noches,
            fines_semana_exactos=self.fines_semana_exactos,
            es_jefe_equipo=self.es_jefe_equipo,
            prioridad_jefe=self.prioridad_jefe,
            notas=self.notas,
        )


# ---------------------------------------------------------------------------
# EQUIPO ACTUAL DEL CENTRO (AV. SAN LUIS 77) — julio de 2026.
# Fuente de la verdad de la plantilla. Modificar aquí (o desde la interfaz) para
# reflejar altas y bajas del equipo.
# ---------------------------------------------------------------------------
EQUIPO_ACTUAL: list[_PlantillaTrabajador] = [
    # Luis y Fernando son JEFES DE EQUIPO: pueden realizar cualquier puesto SIEMPRE
    # que sea de mañana (nunca noches) y trabajan exactamente un fin de semana al
    # mes. Además, el puesto F1 de mañana en día laborable queda reservado a ellos
    # (en fin de semana o festivo lo puede hacer cualquiera).
    _PlantillaTrabajador(
        "FERNANDO CEMBRERO ANTOLÍN", set(_TODOS), set(), puede_hacer_noches=False,
        fines_semana_exactos=1, es_jefe_equipo=True, prioridad_jefe=1,
        notas="Jefe de equipo. Cualquier puesto de mañana. Nunca noches. Un fin de "
              "semana al mes. F1 de mañana en laborable reservado a jefes."),
    _PlantillaTrabajador(
        "LUIS PERALTA ROS", set(_TODOS), set(), puede_hacer_noches=False,
        fines_semana_exactos=1, es_jefe_equipo=True, prioridad_jefe=2,
        notas="Jefe de equipo. Cualquier puesto de mañana. Nunca noches. Un fin de "
              "semana al mes. F1 de mañana en laborable reservado a jefes. Recibe el "
              "día extra de MT-F1 cuando el reparto no es par (prioridad mayor)."),
    _PlantillaTrabajador(
        "MOHAMED AMAR MOHAMED", {Puesto.MO}, {Puesto.F1, Puesto.F2},
        notas="Solo MO de mañana o cualquier puesto de noche. Nunca F1/F2/EX-MT."),
    # Resto del equipo (polivalente).
    _PlantillaTrabajador("EUGENIA DEL PILAR VILEMA VILEMA"),
    _PlantillaTrabajador("SANTIAGO R. MANRIQUE GÓMEZ"),
    _PlantillaTrabajador("DANIEL LABERNIA GONZÁLEZ"),
    _PlantillaTrabajador("JAVIER CALDERON FERNÁNDEZ"),
    _PlantillaTrabajador("Mª VICTORIA CANO MARTINEZ"),
    _PlantillaTrabajador("JAVIER PEREZ GALLARDO"),
    _PlantillaTrabajador("IVÁN DÍAZ MOYA"),
]


def cargar_plantilla_ejemplo(servicio: ServicioCuadrantes) -> int:
    """Carga el equipo actual si la base de datos está vacía.

    :return: número de trabajadores creados (0 si ya existían).
    """
    if servicio.trabajadores.listar():
        return 0
    for definicion in EQUIPO_ACTUAL:
        servicio.trabajadores.guardar(definicion.a_trabajador())
    return len(EQUIPO_ACTUAL)


def sincronizar_equipo(servicio: ServicioCuadrantes) -> dict[str, list[str]]:
    """Reconcilia la plantilla existente con el :data:`EQUIPO_ACTUAL`.

    * Da de **alta** a los trabajadores del equipo actual que no existan.
    * **Reactiva** y actualiza restricciones de los que existan pero estén
      inactivos o desactualizados.
    * **Desactiva** (nunca borra) a los que ya no forman parte del equipo actual,
      de modo que el histórico de cuadrantes se conserva íntegro.

    :return: diccionario con las listas de nombres «altas», «reactivados» y
        «desactivados» para informar al usuario.
    """
    existentes = {t.nombre: t for t in servicio.trabajadores.listar()}
    nombres_actuales = {d.nombre for d in EQUIPO_ACTUAL}
    resultado = {"altas": [], "reactivados": [], "desactivados": []}

    # Altas y actualizaciones.
    for definicion in EQUIPO_ACTUAL:
        actual = existentes.get(definicion.nombre)
        if actual is None:
            servicio.trabajadores.guardar(definicion.a_trabajador())
            resultado["altas"].append(definicion.nombre)
        else:
            cambiado = not actual.activo
            actual.activo = True
            # Actualizar restricciones según la definición del equipo actual.
            actual.puestos_diurnos_permitidos = set(definicion.puestos_diurnos)
            actual.puestos_nocturnos_permitidos = set(definicion.puestos_nocturnos)
            actual.puede_hacer_noches = definicion.puede_hacer_noches
            actual.fines_semana_exactos = definicion.fines_semana_exactos
            servicio.trabajadores.guardar(actual)
            if cambiado:
                resultado["reactivados"].append(definicion.nombre)

    # Bajas: desactivar (no borrar) a quien ya no está en el equipo.
    for nombre, trabajador in existentes.items():
        if nombre not in nombres_actuales and trabajador.activo:
            trabajador.activo = False
            servicio.trabajadores.guardar(trabajador)
            resultado["desactivados"].append(nombre)

    return resultado
