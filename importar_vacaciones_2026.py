#!/usr/bin/env python3
"""
Importa a la base de datos la HOJA DE VACACIONES 2026 del centro.

Ejecútelo cuando haga falta rehacer la base de datos:

    python importar_vacaciones_2026.py

Los periodos están tomados de las casillas «de … al …» del planning oficial
(AVDA. SAN LUIS, 77). Se toman LOS RANGOS, no los contadores de días de la fila
de arriba: en varias filas no coinciden, y el rango es lo que de verdad se
disfruta. Las diferencias detectadas se avisan al final.

Es idempotente: borra las vacaciones de 2026 que ya hubiera de cada trabajador
antes de volver a insertarlas, de modo que puede ejecutarse las veces que haga
falta sin duplicar nada.
"""

from __future__ import annotations

import unicodedata
from datetime import date

from cuadrantes.config.constantes import TipoAusencia
from cuadrantes.datos.modelos import Ausencia
from cuadrantes.rutas import ruta_base_datos
from cuadrantes.servicio import ServicioCuadrantes

# { nombre en la hoja: [(mes, dia_inicio, dia_fin), ...] }
# Un periodo a caballo entre dos meses se parte en dos tramos, uno por mes.
VACACIONES_2026: dict[str, list[tuple[int, int, int]]] = {
    "FERNANDO CEMBRERO ANTOLIN": [(3, 25, 31), (4, 1, 1), (8, 24, 31), (9, 1, 8),
                                  (11, 23, 29)],
    "DANIEL LABERNIA GONZALEZ": [(4, 6, 13), (9, 1, 16), (11, 2, 8)],
    "LUIS PERALTA ROS": [(5, 25, 31), (6, 1, 1), (7, 27, 31), (8, 1, 3), (8, 24, 31),
                         (11, 16, 23)],
    "JAVIER PEREZ GALLARDO": [(5, 24, 31), (7, 17, 31), (11, 23, 30)],
    "JAVIER CALDERON FERNANDEZ": [(6, 16, 30), (9, 7, 14), (12, 1, 8)],
    "MARIA VICTORIA CANO MARTINEZ": [(1, 7, 14), (4, 23, 30), (6, 23, 30), (8, 3, 9)],
    "SANTIAGO REYES MANRIQUE GOMEZ": [(3, 30, 31), (4, 1, 5), (8, 1, 16), (10, 5, 12)],
    "EUGENIA DEL PILAR VILEMA VILEMA": [(8, 22, 31), (9, 1, 6), (12, 7, 9)],
    "IVAN DIAZ MOYA": [(7, 16, 31), (11, 16, 23)],
    "MOHAMED AMAR MOHAMED": [(7, 13, 19), (8, 10, 16), (10, 30, 31), (11, 1, 6),
                             (12, 9, 12)],
}

# Días que declara el contador de la hoja, por si hay que cuadrar con RR. HH.
# Donde no coincide con los rangos, mandan los rangos (ver docstring).
SALDO_DECLARADO = {
    "FERNANDO CEMBRERO ANTOLIN": 31, "DANIEL LABERNIA GONZALEZ": 31,
    "LUIS PERALTA ROS": 31, "JAVIER PEREZ GALLARDO": 31,
    "JAVIER CALDERON FERNANDEZ": 31, "MARIA VICTORIA CANO MARTINEZ": 31,
    "SANTIAGO REYES MANRIQUE GOMEZ": 31, "EUGENIA DEL PILAR VILEMA VILEMA": 19,
    "IVAN DIAZ MOYA": 23, "MOHAMED AMAR MOHAMED": 26,
}


def _norm(nombre: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", nombre)
                if unicodedata.category(c) != "Mn")
    return " ".join(s.upper().replace("ª", "A").split())


# Los nombres de la hoja no siempre coinciden con los de la plantilla.
_EQUIVALENCIAS = {
    "MARIA VICTORIA CANO MARTINEZ": "MA VICTORIA CANO MARTINEZ",
    "SANTIAGO REYES MANRIQUE GOMEZ": "SANTIAGO R. MANRIQUE GOMEZ",
}


def main() -> int:
    servicio = ServicioCuadrantes(str(ruta_base_datos()))
    por_norma = {_norm(t.nombre): t for t in servicio.trabajadores.listar()}

    avisos: list[str] = []
    total = 0
    for nombre, periodos in VACACIONES_2026.items():
        clave = _norm(_EQUIVALENCIAS.get(nombre, nombre))
        trabajador = por_norma.get(clave)
        if trabajador is None:
            # Coincidencia por nombre y primer apellido, que es como se distinguen.
            partes = _norm(nombre).split()
            trabajador = next(
                (t for k, t in por_norma.items() if k.split()[:2] == partes[:2]), None)
        if trabajador is None:
            avisos.append(f"{nombre}: no está en la plantilla, se omite")
            continue

        # Idempotencia: fuera las vacaciones de 2026 que ya tuviera cargadas.
        for mes_previo in range(1, 13):
            for existente in servicio.ausencias.listar_por_mes(2026, mes_previo):
                if (existente.trabajador_id == trabajador.id
                        and existente.tipo is TipoAusencia.VACACIONES
                        and existente.id is not None):
                    servicio.ausencias.eliminar(existente.id)
        dias = 0
        for mes, inicio, fin in periodos:
            servicio.ausencias.guardar(Ausencia(
                id=None, trabajador_id=trabajador.id, tipo=TipoAusencia.VACACIONES,
                fecha_inicio=date(2026, mes, inicio), fecha_fin=date(2026, mes, fin),
                descripcion="Planning de vacaciones 2026"))
            dias += fin - inicio + 1
            total += 1
        declarado = SALDO_DECLARADO.get(nombre)
        if declarado is not None and declarado != dias:
            avisos.append(f"{nombre}: los rangos suman {dias} días y la hoja declara "
                          f"{declarado}; se han cargado los {dias} de los rangos")
        print(f"  {trabajador.nombre[:34]:36} {len(periodos)} periodos, {dias} días")

    print(f"\n✅ {total} periodos de vacaciones de 2026 guardados.")
    for aviso in avisos:
        print(f"  ⚠ {aviso}")
    servicio.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
