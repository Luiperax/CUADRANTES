#!/usr/bin/env python3
"""
Importa el cuadrante REAL de agosto de 2026 al historial.

Ejecútelo UNA vez en el portátil, dentro de la carpeta del programa:

    python importar_agosto_2026.py

Añade el cuadrante de agosto de 2026 (transcrito del PDF original) al historial,
para que el reparto de los próximos meses tenga en cuenta quién trabajó en agosto
(horas, noches, fines de semana y festivos).

La transcripción se ha verificado contra los totales del PDF (H.T., H.E. y H.N. de
cada trabajador). Al terminar, abra agosto en el programa y revise visualmente por
si hubiera que ajustar alguna celda concreta.
"""

from __future__ import annotations

import unicodedata
from datetime import date

from cuadrantes.config.constantes import EstadoCuadrante, Puesto, TipoAusencia, Turno
from cuadrantes.datos.datos_iniciales import cargar_plantilla_ejemplo
from cuadrantes.datos.modelos import Asignacion, Cuadrante, Trabajador
from cuadrantes.dominio.computos import calcular_resumenes
from cuadrantes.rutas import ruta_base_datos
from cuadrantes.servicio import ServicioCuadrantes

# Cada trabajador: lista de 31 celdas (día 1..31). Cada celda es:
#   "MT/F1", "TN/F2", "MT/MO", "MT/EX"...  -> turno/puesto
#   "V"  -> vacaciones ;  "."  -> libre/descanso
AGOSTO = {
 "FERNANDO CEMBRERO ANTOLÍN":
   ". . MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 . . MT/F1 MT/F1 MT/EX MT/F2 MT/EX . . "
   "MT/F1 MT/F1 MT/F1 MT/EX . . . V V V V V V V V",
 "EUGENIA DEL PILAR VILEMA VILEMA":
   "TN/F2 TN/F1 TN/F2 TN/F2 TN/F2 . MT/EX MT/F1 MT/F2 MT/EX MT/MO . . . . . "
   "MT/MO TN/F1 . . MT/MO V V V V V V V V V V",
 "SANTIAGO R. MANRIQUE GÓMEZ":
   "V V V V V V V V V V V V V V V V . . MT/F2 MT/MO MT/EX . . MT/EX MT/EX "
   "MT/MO MT/F2 MT/MO MT/F2 MT/F2 .",
 "DANIEL LABERNIA GONZÁLEZ":
   ". . . . . MT/EX TN/F1 TN/F2 TN/F1 TN/F1 TN/F2 TN/F1 . . . . TN/F2 TN/F2 . . . "
   "MT/F2 MT/F1 MT/F2 . MT/EX . MT/F2 . . .",
 "Mª VICTORIA CANO MARTINEZ":
   ". . V V V V V V V MT/F2 TN/F1 TN/F2 TN/F2 TN/F2 TN/F2 TN/F1 . . . . TN/F2 TN/F2 "
   "TN/F1 TN/F2 TN/F2 TN/F1 TN/F1 . . . MT/EX",
 "JAVIER PEREZ GALLARDO":
   ". . . TN/F1 TN/F1 TN/F2 . . . . . MT/MO TN/F1 TN/F1 TN/F1 TN/F2 TN/F1 . TN/F1 TN/F2 . "
   ". . MT/MO MT/MO . MT/EX TN/F1 TN/F2 TN/F1 TN/F1",
 "LUIS PERALTA ROS":
   "V V V V V V V V V V V MT/F1 MT/F1 MT/F1 . . . . . MT/F1 MT/F1 . . MT/F1 MT/F1 "
   "MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 MT/F1",
 "JAVIER CALDERON FERNÁNDEZ":
   ". . MT/F2 MT/EX MT/EX . MT/F2 MT/F2 MT/F1 . MT/EX MT/F2 MT/EX MT/MO . . MT/F2 MT/EX "
   "MT/MO . MT/F2 . . . MT/F2 MT/F2 MT/MO MT/EX . . MT/F2",
 "MOHAMED AMAR MOHAMED":
   "TN/F1 TN/F2 TN/F1 . MT/MO MT/MO MT/MO . . V V V V V V V . MT/MO TN/F1 TN/F2 TN/F1 "
   "TN/F1 TN/F2 TN/F1 . . MT/MO . . . MT/MO",
 "IVAN DIAZ MOYA":
   "MT/F2 MT/F1 MT/EX MT/MO MT/F2 MT/F2 . . . MT/MO MT/F2 . . MT/F2 MT/F2 MT/F1 . MT/F2 "
   "MT/EX MT/F2 . MT/F1 MT/F2 . . . . . . . .",
 "ALICIA GUTIERREZ SANCHEZ":
   "MT/F1 MT/F2 MT/MO MT/F2 . TN/F1 TN/F2 TN/F1 TN/F2 TN/F2 . . MT/MO . MT/F1 MT/F2 MT/EX . . . . "
   ". . . TN/F1 TN/F2 TN/F2 TN/F2 TN/F1 TN/F2 TN/F2",
}


def _parsear_celda(token: str):
    """Convierte un token en (turno, puesto, ausencia)."""
    if token == ".":
        return None, None, TipoAusencia.LIBRE
    if token == "V":
        return None, None, TipoAusencia.VACACIONES
    turno_txt, puesto_txt = token.split("/")
    return Turno(turno_txt), Puesto(puesto_txt), None


def construir_cuadrante(mapa_nombres: dict[str, int]) -> Cuadrante:
    cuad = Cuadrante(
        id=None, anio=2026, mes=8, empresa="NATURGY", sede="AV. SAN LUIS - 77",
        computo_mensual=162.0, estado=EstadoCuadrante.VALIDADO, fecha_generacion=date.today(),
        trabajadores_ids=[mapa_nombres[n] for n in AGOSTO],
    )
    for nombre, cadena in AGOSTO.items():
        tid = mapa_nombres[nombre]
        celdas = cadena.split()
        if len(celdas) != 31:
            raise ValueError(f"{nombre}: {len(celdas)} celdas (deben ser 31)")
        for i, token in enumerate(celdas):
            dia = i + 1
            turno, puesto, ausencia = _parsear_celda(token)
            cuad.establecer(Asignacion(tid, dia, turno=turno, puesto=puesto, ausencia=ausencia))
    return cuad


def _normalizar(nombre: str) -> str:
    """Nombre en mayúsculas y sin tildes, para emparejar aunque cambien los acentos.

    Así "IVAN DIAZ MOYA" (como aparece en el PDF) se reconoce como "IVÁN DÍAZ MOYA"
    (como está en la plantilla) y no se crea un trabajador duplicado.
    """
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", nombre)
        if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.upper().split())


def main() -> int:
    servicio = ServicioCuadrantes(str(ruta_base_datos()))
    cargar_plantilla_ejemplo(servicio)

    # Emparejar cada nombre del cuadrante con el trabajador ya existente (ignorando
    # tildes y mayúsculas). Si no existe ninguno equivalente, se crea (p. ej. Alicia).
    por_norma = {_normalizar(t.nombre): t for t in servicio.trabajadores.listar()}
    todos = set(Puesto)
    mapa: dict[str, int] = {}
    for nombre in AGOSTO:
        existente = por_norma.get(_normalizar(nombre))
        if existente is None:
            existente = servicio.trabajadores.guardar(Trabajador(
                id=None, nombre=nombre,
                puestos_diurnos_permitidos=set(todos),
                puestos_nocturnos_permitidos={Puesto.F1, Puesto.F2},
                notas="Añadido al importar agosto 2026."))
            por_norma[_normalizar(nombre)] = existente
        mapa[nombre] = existente.id

    cuad = construir_cuadrante(mapa)

    # Verificación contra los totales del PDF antes de guardar.
    esperado = {
        "FERNANDO CEMBRERO ANTOLÍN": (168, 0, 8),
        "EUGENIA DEL PILAR VILEMA VILEMA": (156, 48, 10),
        "SANTIAGO R. MANRIQUE GÓMEZ": (120, 0, 16),
        "DANIEL LABERNIA GONZÁLEZ": (168, 64, 0),
        "Mª VICTORIA CANO MARTINEZ": (180, 104, 7),
        "JAVIER PEREZ GALLARDO": (216, 112, 0),
        "LUIS PERALTA ROS": (156, 0, 11),
        "JAVIER CALDERON FERNÁNDEZ": (228, 0, 0),
        "MOHAMED AMAR MOHAMED": (180, 72, 7),
        "IVAN DIAZ MOYA": (192, 0, 0),
        "ALICIA GUTIERREZ SANCHEZ": (240, 96, 0),
    }
    trab = {t.id: t for t in servicio.trabajadores.listar()}
    resumenes = calcular_resumenes(cuad, trab)
    print(f"{'Trabajador':32}{'H.T.':>6}{'H.N.':>6}{'Vac':>5}   ¿coincide con el PDF?")
    todo_ok = True
    for nombre in AGOSTO:
        tid = mapa[nombre]
        r = resumenes[tid]
        ht_ok = abs(r.horas_trabajadas - esperado[nombre][0]) < 0.5
        hn_ok = abs(r.horas_nocturnas - esperado[nombre][1]) < 0.5
        v_ok = r.dias_ausencia_computable == esperado[nombre][2]
        ok = ht_ok and hn_ok and v_ok
        todo_ok = todo_ok and ok
        print(f"{nombre:32}{r.horas_trabajadas:>6.0f}{r.horas_nocturnas:>6.0f}"
              f"{r.dias_ausencia_computable:>5}   {'OK' if ok else 'REVISAR'}")

    if not todo_ok:
        print("\n⚠️  Hay diferencias con el PDF. No se guarda para no meter datos erróneos.")
        servicio.cerrar()
        return 1

    # Si ya existía un agosto de 2026 en el historial, se reemplaza (evita duplicados
    # al ejecutar el script más de una vez).
    existente = servicio.cuadrantes.ultima_version(2026, 8)
    if existente is not None:
        cuad.id = existente.id
        cuad.version = existente.version
        print("\nℹ️  Ya había un agosto de 2026 en el historial; se reemplaza.")

    servicio.cuadrantes.guardar(cuad)
    print("\n✅ Agosto de 2026 añadido al historial correctamente.")
    print("   Ábralo en el programa para revisarlo visualmente.")
    servicio.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
