"""Interfaz de línea de comandos del sistema de XAU/USD.

Ejemplos:
    python -m oro.cli senal                 Analiza el mercado y muestra la señal (o «no hay»).
    python -m oro.cli backtest --velas 8000 Ejecuta un backtest y muestra las métricas.
    python -m oro.cli entrenar              Entrena el modelo con validación walk-forward.
    python -m oro.cli demo                  Demostración de extremo a extremo.
    python -m oro.cli servir                Arranca la API/panel (requiere uvicorn).
"""

from __future__ import annotations

import argparse
import sys

from .config import cargar_configuracion
from .datos import ProveedorCSV, ProveedorSintetico
from .servicio import ServicioOro

_AVISO = ("Aviso: herramienta de análisis, no asesoramiento financiero. "
          "El trading conlleva riesgo de pérdida del capital.")


def _proveedor(args):
    if getattr(args, "csv", None):
        return ProveedorCSV(args.csv)
    return ProveedorSintetico(velas=max(args.velas, 8000), semilla=args.semilla)


def _cmd_senal(args) -> int:
    servicio = ServicioOro(cargar_configuracion(), _proveedor(args))
    r = servicio.analizar_ahora(args.velas)
    print(_AVISO, "\n")
    if r.hay_operacion and r.signal is not None:
        print("✔ OPORTUNIDAD A+ DETECTADA\n")
        print(r.signal.resumen())
        print("\nMotivos de entrada:")
        for m in r.signal.motivos_entrada:
            print(f"  • {m}")
        print(f"\nContexto: {r.signal.contexto_tecnico}")
        print(f"Tamaño sugerido: {r.signal.tamano_posicion:.2f} oz")
    else:
        print(f"✖ {r.mensaje}")
        for m in r.motivos_no:
            print(f"  • {m}")
    return 0


def _cmd_backtest(args) -> int:
    servicio = ServicioOro(cargar_configuracion(), _proveedor(args))
    print("Ejecutando backtest… (puede tardar)")
    res = servicio.backtest(args.velas)
    print("\n" + res.resumen())
    print(_AVISO)
    return 0


def _cmd_entrenar(args) -> int:
    servicio = ServicioOro(cargar_configuracion(), _proveedor(args))
    print("Entrenando y validando (walk-forward)…")
    informe = servicio.entrenar(args.velas, aceptar_si_valido=not args.forzar)
    for k, v in informe.items():
        print(f"  {k}: {v}")
    return 0


def _cmd_demo(args) -> int:
    print("=" * 64)
    print("  DEMO — Sistema de análisis XAU/USD (datos SINTÉTICOS)")
    print("=" * 64)
    print(_AVISO, "\n")
    servicio = ServicioOro(cargar_configuracion(), ProveedorSintetico(velas=8000, semilla=args.semilla))
    print("1) Backtest sobre el histórico sintético:")
    res = servicio.backtest(8000)
    print("   " + res.resumen())
    print("\n2) Análisis del estado de mercado más reciente:")
    r = servicio.analizar_ahora(500)
    if r.hay_operacion and r.signal is not None:
        print("   " + r.signal.resumen())
    else:
        print(f"   {r.mensaje}")
        for m in r.motivos_no[:3]:
            print(f"     • {m}")
    print("\nNota: los datos son sintéticos; las métricas NO son indicativas de")
    print("resultados reales. Conecte datos reales y valide en demo antes de operar.")
    return 0


def _cmd_servir(args) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn no está instalado. Instale con: pip install 'uvicorn[standard]' fastapi")
        return 1
    from .api import crear_app

    app = crear_app()
    print(f"Panel disponible en http://{args.host}:{args.port}/oro/panel")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sistema de análisis de XAU/USD (ORO)")
    parser.add_argument("--velas", type=int, default=6000, help="Nº de velas a usar.")
    parser.add_argument("--semilla", type=int, default=42, help="Semilla del proveedor sintético.")
    parser.add_argument("--csv", type=str, default=None, help="Ruta a un CSV OHLCV real.")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("senal", help="Analiza el mercado actual.")
    sub.add_parser("backtest", help="Ejecuta un backtest.")
    p_ent = sub.add_parser("entrenar", help="Entrena el modelo con validación.")
    p_ent.add_argument("--forzar", action="store_true", help="Guardar aunque no supere la validación.")
    sub.add_parser("demo", help="Demostración de extremo a extremo.")
    p_srv = sub.add_parser("servir", help="Arranca la API/panel.")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8010)

    args = parser.parse_args(argv)
    despacho = {
        "senal": _cmd_senal, "backtest": _cmd_backtest, "entrenar": _cmd_entrenar,
        "demo": _cmd_demo, "servir": _cmd_servir,
    }
    return despacho[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
