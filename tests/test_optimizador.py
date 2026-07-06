"""Pruebas del motor de optimización con un escenario realista (11 trabajadores)."""

from __future__ import annotations

from datetime import date

from cuadrantes.config.configuracion import Configuracion
from cuadrantes.config.constantes import Puesto, TipoAusencia
from cuadrantes.datos.modelos import Ausencia, Trabajador
from cuadrantes.motor.optimizador import OptimizadorCuadrante


def _plantilla_naturgy() -> list[Trabajador]:
    """Reproduce la plantilla y restricciones individuales del cuadrante real."""
    todos = set(Puesto)
    trabajadores: list[Trabajador] = []
    idx = 1

    def nuevo(nombre, diurnos, nocturnos, noches=True, **kw):
        nonlocal idx
        t = Trabajador(
            id=idx, nombre=nombre,
            puestos_diurnos_permitidos=set(diurnos),
            puestos_nocturnos_permitidos=set(nocturnos),
            puede_hacer_noches=noches, **kw,
        )
        trabajadores.append(t)
        idx += 1
        return t

    # Restricciones individuales exigidas por el pliego:
    nuevo("FERNANDO CEMBRERO ANTOLÍN", {Puesto.F1}, set(), noches=False)
    nuevo("LUIS PERALTA ROS", {Puesto.F1}, set(), noches=False)
    nuevo("MOHAMED AMAR MOHAMED", {Puesto.MO}, {Puesto.F1, Puesto.F2})
    # Resto de la plantilla: polivalentes.
    nuevo("SANTIAGO R. MANRIQUE GÓMEZ", todos, {Puesto.F1, Puesto.F2})
    nuevo("DANIEL LABERNIA GONZÁLEZ", todos, {Puesto.F1, Puesto.F2})
    nuevo("JAVIER CALDERON FERNÁNDEZ", todos, {Puesto.F1, Puesto.F2})
    nuevo("Mª VICTORIA CANO MARTINEZ", todos, {Puesto.F1, Puesto.F2})
    nuevo("JAVIER PEREZ GALLARDO", todos, {Puesto.F1, Puesto.F2})
    nuevo("JUAN ANTONIO MOLINA SEVILLA", todos, {Puesto.F1, Puesto.F2})
    nuevo("IVAN DIAZ MOYA", todos, {Puesto.F1, Puesto.F2})
    nuevo("RAUL PARRA MIGUEL", todos, {Puesto.F1, Puesto.F2})
    return trabajadores


def test_genera_cuadrante_cubierto():
    trabajadores = _plantilla_naturgy()
    config = Configuracion()
    config.tiempo_maximo_solver_segundos = 20

    # Una trabajadora de vacaciones parte del mes.
    ausencias = [
        Ausencia(id=1, trabajador_id=7, tipo=TipoAusencia.VACACIONES,
                 fecha_inicio=date(2026, 1, 3), fecha_fin=date(2026, 1, 12)),
    ]

    optimizador = OptimizadorCuadrante(
        2026, 1, trabajadores, config, ausencias=ausencias,
    )
    resultado = optimizador.resolver()

    print(f"Estado solver: {resultado.estado_solver}")
    print(f"Puestos sin cubrir: {len(resultado.puestos_sin_cubrir)}")
    print(f"Tiempo: {resultado.tiempo_segundos:.2f}s  Objetivo: {resultado.valor_objetivo}")

    assert resultado.estado_solver in ("OPTIMAL", "FEASIBLE")
    # No debe quedar ningún puesto sin cubrir en un escenario holgado.
    assert not resultado.puestos_sin_cubrir, resultado.puestos_sin_cubrir

    # Verificación de restricciones individuales sobre el resultado.
    cuad = resultado.cuadrante
    for (t_id, dia), asig in cuad.asignaciones.items():
        trab = next(x for x in trabajadores if x.id == t_id)
        if asig.es_trabajo:
            assert trab.puede_realizar(asig.turno, asig.puesto), (
                f"{trab.nombre} asignado a {asig.turno}-{asig.puesto} no permitido")
    # Luis y Fernando nunca de noche.
    for t_id in (1, 2):
        noches = [a for (tt, _), a in cuad.asignaciones.items() if tt == t_id and a.es_noche]
        assert not noches, "Luis/Fernando no deben tener noches"

    print("OK: cuadrante válido y restricciones individuales respetadas")
    return resultado


if __name__ == "__main__":
    test_genera_cuadrante_cubierto()
