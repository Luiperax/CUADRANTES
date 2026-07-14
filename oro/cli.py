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
from .datos import ProveedorCSV, ProveedorSintetico, ProveedorYahoo
from .servicio import ServicioOro

_AVISO = ("Aviso: herramienta de análisis, no asesoramiento financiero. "
          "El trading conlleva riesgo de pérdida del capital.")


def _proveedor(args):
    if getattr(args, "csv", None):
        return ProveedorCSV(args.csv)
    if getattr(args, "sintetico", False):
        return ProveedorSintetico(velas=max(args.velas, 8000), semilla=args.semilla)
    return ProveedorSintetico(velas=max(args.velas, 8000), semilla=args.semilla)


def _proveedor_vivo(args):
    """Proveedor para el modo en vivo: real (Yahoo) salvo que se pida sintético."""
    if getattr(args, "csv", None):
        return ProveedorCSV(args.csv)
    if getattr(args, "sintetico", False):
        return ProveedorSintetico(velas=8000, semilla=args.semilla)
    cfg = cargar_configuracion()
    return ProveedorYahoo(timeframe=cfg.timeframe)


def _construir_notificador():
    """Compone los canales de notificación disponibles según el entorno."""
    import os

    from .notificaciones import (
        NotificadorConsola,
        NotificadorEmail,
        NotificadorMultiple,
        NotificadorTelegram,
        NotificadorWebhook,
    )

    canales = [NotificadorConsola()]
    if os.getenv("ORO_TELEGRAM_TOKEN") and os.getenv("ORO_TELEGRAM_CHAT_ID"):
        canales.append(NotificadorTelegram())
    if os.getenv("ORO_WEBHOOK_URL"):
        canales.append(NotificadorWebhook())
    if os.getenv("ORO_SMTP_HOST"):
        canales.append(NotificadorEmail())
    return NotificadorMultiple(canales)


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


def _cmd_vivo(args) -> int:
    from .vivo import RunnerVivo

    proveedor = _proveedor_vivo(args)
    notificador = _construir_notificador()
    runner = RunnerVivo(
        cargar_configuracion(), proveedor=proveedor, notificador=notificador,
        max_concurrentes=args.max_concurrentes,
        usar_sentimiento=not args.sin_sentimiento,
    )
    print(_AVISO, "\n")
    print(f"Notificando por: {len(notificador._canales)} canal(es). "
          f"Configura ORO_TELEGRAM_TOKEN/CHAT_ID, ORO_WEBHOOK_URL o ORO_SMTP_* para el móvil.\n")
    runner.ejecutar(intervalo_seg=args.intervalo, max_ciclos=args.max_ciclos)
    return 0


def _cmd_sentimiento(args) -> int:
    from .sentimiento import AnalizadorSentimiento

    print("Analizando prensa financiera y calendario económico…\n")
    ctx = AnalizadorSentimiento(min_titulares_senal=1).analizar()
    print(ctx.resumen())
    if ctx.titulares_destacados:
        print("\nTitulares destacados:")
        for t in ctx.titulares_destacados:
            print(f"  • {t}")
    if ctx.riesgo_noticia_alta:
        print(f"\n⚠ NO OPERAR: evento de alto impacto en ~{ctx.minutos_al_evento} min "
              f"({ctx.proximo_evento}).")
    print("\n" + _AVISO)
    return 0


def _cmd_servir(args) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn no está instalado. Instale con: pip install 'uvicorn[standard]' fastapi")
        return 1

    if args.vivo:
        # Panel EN VIVO: el motor corre en segundo plano y notifica al móvil.
        from .api.vivo_web import crear_app_vivo
        from .vivo import RunnerVivo

        runner = RunnerVivo(
            cargar_configuracion(), proveedor=_proveedor_vivo(args),
            notificador=_construir_notificador(),
        )
        app = crear_app_vivo(runner, intervalo=args.intervalo)
        print(_AVISO)
        print(f"Panel EN VIVO en http://{args.host}:{args.port}/oro/panel "
              f"(revisión cada {args.intervalo}s).")
    else:
        from .api import crear_app

        app = crear_app()
        print(f"Panel (bajo demanda) en http://{args.host}:{args.port}/oro/panel")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sistema de análisis de XAU/USD (ORO)")
    parser.add_argument("--velas", type=int, default=6000, help="Nº de velas a usar.")
    parser.add_argument("--semilla", type=int, default=42, help="Semilla del proveedor sintético.")
    parser.add_argument("--csv", type=str, default=None, help="Ruta a un CSV OHLCV real.")
    parser.add_argument("--sintetico", action="store_true",
                        help="Forzar datos sintéticos (offline) en vez de datos reales.")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("senal", help="Analiza el mercado actual.")
    sub.add_parser("backtest", help="Ejecuta un backtest.")
    p_ent = sub.add_parser("entrenar", help="Entrena el modelo con validación.")
    p_ent.add_argument("--forzar", action="store_true", help="Guardar aunque no supere la validación.")
    sub.add_parser("demo", help="Demostración de extremo a extremo.")
    sub.add_parser("sentimiento", help="Muestra el sentimiento de prensa y el riesgo de noticias.")
    p_vivo = sub.add_parser("vivo", help="Bucle en vivo: entradas, salidas y notificaciones.")
    p_vivo.add_argument("--intervalo", type=int, default=900, help="Segundos entre ciclos (900 = 15 min).")
    p_vivo.add_argument("--max-ciclos", type=int, default=None, dest="max_ciclos",
                        help="Nº máximo de ciclos (por defecto, indefinido).")
    p_vivo.add_argument("--max-concurrentes", type=int, default=2, dest="max_concurrentes",
                        help="Máximo de operaciones abiertas a la vez.")
    p_vivo.add_argument("--sin-sentimiento", action="store_true", dest="sin_sentimiento",
                        help="No consultar prensa/calendario (solo técnico).")
    p_srv = sub.add_parser("servir", help="Arranca la API/panel.")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8010)
    p_srv.add_argument("--vivo", action="store_true",
                       help="Panel EN VIVO: motor en segundo plano + notificaciones.")
    p_srv.add_argument("--intervalo", type=int, default=900,
                       help="Segundos entre ciclos del panel en vivo (900 = 15 min).")

    args = parser.parse_args(argv)
    despacho = {
        "senal": _cmd_senal, "backtest": _cmd_backtest, "entrenar": _cmd_entrenar,
        "demo": _cmd_demo, "sentimiento": _cmd_sentimiento, "vivo": _cmd_vivo,
        "servir": _cmd_servir,
    }
    return despacho[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
