"""
Datos iniciales de ejemplo (plantilla NATURGY - AV. SAN LUIS 77).

Permite arrancar la aplicación con una plantilla realista que ya incorpora las
restricciones individuales exigidas por el pliego. Solo se cargan si la base de
datos no contiene todavía ningún trabajador.
"""

from __future__ import annotations

from ..config.constantes import Puesto
from ..datos.modelos import Trabajador
from ..servicio import ServicioCuadrantes


def cargar_plantilla_ejemplo(servicio: ServicioCuadrantes) -> int:
    """Carga la plantilla de ejemplo si la base de datos está vacía.

    :return: número de trabajadores creados (0 si ya existían).
    """
    if servicio.trabajadores.listar():
        return 0

    todos = set(Puesto)
    plantilla: list[Trabajador] = []

    def nuevo(nombre, diurnos, nocturnos, noches=True, notas="", fines_semana_exactos=None):
        plantilla.append(Trabajador(
            id=None, nombre=nombre,
            puestos_diurnos_permitidos=set(diurnos),
            puestos_nocturnos_permitidos=set(nocturnos),
            puede_hacer_noches=noches, notas=notas,
            fines_semana_exactos=fines_semana_exactos,
        ))

    # --- Restricciones individuales del pliego ---
    # Luis y Fernando son los únicos que trabajan exactamente un fin de semana al mes.
    nuevo("FERNANDO CEMBRERO ANTOLÍN", {Puesto.F1}, set(), noches=False,
          fines_semana_exactos=1,
          notas="Solo F1-MT. Nunca noches. Exactamente un fin de semana al mes.")
    nuevo("LUIS PERALTA ROS", {Puesto.F1}, set(), noches=False,
          fines_semana_exactos=1,
          notas="Solo F1-MT. Nunca noches. Exactamente un fin de semana al mes.")
    nuevo("MOHAMED AMAR MOHAMED", {Puesto.MO}, {Puesto.F1, Puesto.F2},
          notas="Solo MO de mañana o cualquier puesto de noche. Nunca F1/F2/EX-MT.")

    # --- Resto de la plantilla (polivalente) ---
    # Equipo actual del centro (AV. SAN LUIS 77) a fecha de julio de 2026.
    for nombre in (
        "EUGENIA DEL PILAR VILEMA VILEMA",
        "SANTIAGO R. MANRIQUE GÓMEZ", "DANIEL LABERNIA GONZÁLEZ",
        "JAVIER CALDERON FERNÁNDEZ", "Mª VICTORIA CANO MARTINEZ",
        "JAVIER PEREZ GALLARDO", "IVÁN DÍAZ MOYA",
    ):
        nuevo(nombre, todos, {Puesto.F1, Puesto.F2})

    for trabajador in plantilla:
        servicio.trabajadores.guardar(trabajador)
    return len(plantilla)
