#!/usr/bin/env python3
"""
Punto de entrada del Generador de Cuadrantes de Seguridad Privada.

Uso:
    python main.py                 Abre la interfaz gráfica.
    python main.py --asistente     Abre la interfaz y lanza el asistente del mes siguiente.
    python main.py --generar AAAA MM   Genera (sin interfaz) el cuadrante indicado y lo exporta.
    python main.py --programador   Arranca la interfaz con el programador del día 15 activo.

Este módulo separa la lógica de arranque para que la aplicación pueda usarse tanto
de forma interactiva como automatizada (por ejemplo, desde el Programador de
tareas de Windows el día 15 de cada mes).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RUTA_BD = "datos/cuadrantes.db"


def _generar_sin_interfaz(anio: int, mes: int) -> int:
    """Genera y exporta un cuadrante sin abrir la interfaz (modo automatizado)."""
    from cuadrantes.datos.datos_iniciales import cargar_plantilla_ejemplo
    from cuadrantes.servicio import ServicioCuadrantes

    servicio = ServicioCuadrantes(RUTA_BD)
    cargar_plantilla_ejemplo(servicio)
    print(f"Generando cuadrante {mes:02d}/{anio}…")
    resultado = servicio.generar(anio, mes)
    print(f"  Estado del solucionador: {resultado.estado_solver}")
    print(f"  Estado del cuadrante:    {resultado.cuadrante.estado.descripcion}")
    print(f"  Tiempo:                  {resultado.tiempo_segundos:.1f} s")
    if resultado.puestos_sin_cubrir:
        print(f"  Puestos sin cubrir:      {len(resultado.puestos_sin_cubrir)}")

    salida = Path("exportaciones")
    salida.mkdir(exist_ok=True)
    base = f"Cuadrante_{anio}_{mes:02d}"
    servicio.exportar_excel(resultado.cuadrante, salida / f"{base}.xlsx")
    servicio.exportar_pdf(resultado.cuadrante, salida / f"{base}.pdf")
    servicio.exportar_informes(resultado.cuadrante, salida / f"{base}_informes.pdf")
    servicio.copia_seguridad()
    print(f"  Exportado en: {salida.resolve()}")
    servicio.cerrar()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generador de Cuadrantes de Seguridad Privada")
    parser.add_argument("--asistente", action="store_true",
                        help="Abre la interfaz y lanza el asistente del mes siguiente.")
    parser.add_argument("--programador", action="store_true",
                        help="Activa el programador interno del día 15.")
    parser.add_argument("--generar", nargs=2, metavar=("AAAA", "MM"), type=int,
                        help="Genera y exporta un cuadrante sin interfaz.")
    args = parser.parse_args()

    if args.generar:
        return _generar_sin_interfaz(args.generar[0], args.generar[1])

    # Modo interfaz gráfica.
    from cuadrantes.interfaz.aplicacion import iniciar
    return iniciar(RUTA_BD, lanzar_asistente=args.asistente, activar_programador=args.programador)


if __name__ == "__main__":
    sys.exit(main())
