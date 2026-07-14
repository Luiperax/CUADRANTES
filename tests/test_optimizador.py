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

    # Restricciones individuales exigidas por el pliego. Luis y Fernando son jefes
    # de equipo: cualquier puesto de mañana, nunca noches, un fin de semana al mes,
    # y MT-F1 en laborable reservado a ellos.
    nuevo("FERNANDO CEMBRERO ANTOLÍN", todos, set(), noches=False,
          es_jefe_equipo=True, fines_semana_exactos=1)
    nuevo("LUIS PERALTA ROS", todos, set(), noches=False,
          es_jefe_equipo=True, fines_semana_exactos=1)
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


def test_reglas_noche_viernes_y_vacaciones():
    """Comprueba: (R1) noche de viernes solo con fin de semana completo de noche,
    (R2) sin noche el día previo a las vacaciones."""
    from cuadrantes.dominio.calendario import CalendarioMes

    trabajadores = _plantilla_naturgy()
    config = Configuracion()
    config.tiempo_maximo_solver_segundos = 20

    # Un trabajador que hace noches se va de vacaciones a partir del día 12.
    ausencias = [
        Ausencia(id=1, trabajador_id=5, tipo=TipoAusencia.VACACIONES,
                 fecha_inicio=date(2026, 1, 12), fecha_fin=date(2026, 1, 20)),
    ]

    optimizador = OptimizadorCuadrante(2026, 1, trabajadores, config, ausencias=ausencias)
    resultado = optimizador.resolver()
    assert resultado.estado_solver in ("OPTIMAL", "FEASIBLE")
    assert not resultado.puestos_sin_cubrir, resultado.puestos_sin_cubrir

    cuad = resultado.cuadrante
    cal = CalendarioMes(2026, 1)

    def es_noche(t_id, dia):
        a = cuad.obtener(t_id, dia)
        return a is not None and a.es_noche

    # (R1) Ninguna noche de viernes sin sábado Y domingo también de noche.
    for sabado, domingo in cal.fines_de_semana():
        viernes = sabado - 1
        if viernes < 1:
            continue
        for t in trabajadores:
            if es_noche(t.id, viernes):
                assert es_noche(t.id, sabado) and es_noche(t.id, domingo), (
                    f"{t.nombre} hace noche el viernes {viernes} sin el finde completo")

    # (R2) El día previo al inicio de las vacaciones (día 11) no puede ser noche.
    assert not es_noche(5, 11), "No debe haber noche el día previo a las vacaciones"

    print("OK: reglas de noche de viernes y de vacaciones respetadas")


if __name__ == "__main__":
    test_genera_cuadrante_cubierto()
    test_reglas_noche_viernes_y_vacaciones()
