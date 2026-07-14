"""Una única revisión del mercado (para ejecutar de forma programada).

Pensado para GitHub Actions / cron: cada ejecución carga el estado previo
(operaciones abiertas y contador diario), hace UN ciclo del motor en vivo —que
notifica entradas y salidas por los canales configurados (Telegram, etc.)— y
guarda el estado para la siguiente ejecución.

    python -m oro.alerta

Variables de entorno:
    ORO_ESTADO              ruta del fichero de estado (por defecto oro_estado.json).
    ORO_TELEGRAM_TOKEN,
    ORO_TELEGRAM_CHAT_ID    para recibir los avisos en el móvil por Telegram.
    ORO_CAPITAL, ORO_RIESGO_POR_OPERACION, ...  parámetros (ver oro/config.py).
"""

from __future__ import annotations

import os
import sys

from .cli import _construir_notificador
from .config import cargar_configuracion
from .datos import ProveedorYahoo
from .vivo import RunnerVivo


def _probar_email() -> tuple[bool, str]:
    """Intenta un envío de correo real mostrando el error concreto si falla."""
    import smtplib
    from email.mime.text import MIMEText

    host = os.getenv("ORO_SMTP_HOST", "")
    puerto = int(os.getenv("ORO_SMTP_PUERTO", "587"))
    usuario = os.getenv("ORO_SMTP_USUARIO", "")
    clave = os.getenv("ORO_SMTP_CLAVE", "")
    destino = os.getenv("ORO_SMTP_DESTINO", "")
    if not (host and usuario and destino):
        return False, "faltan ORO_SMTP_HOST / ORO_SMTP_USUARIO / ORO_SMTP_DESTINO"
    msg = MIMEText("Notificación de PRUEBA del sistema XAU/USD. Si lees esto, el correo funciona. "
                   "Recuerda: herramienta de análisis, no asesoramiento financiero.")
    msg["Subject"] = "✅ Prueba de alertas XAU/USD"
    msg["From"] = usuario
    msg["To"] = destino
    try:
        with smtplib.SMTP(host, puerto, timeout=15) as s:
            s.starttls()
            if clave:
                s.login(usuario, clave)
            s.send_message(msg)
        return True, ""
    except Exception as e:  # noqa: BLE001 — queremos ver el motivo exacto.
        return False, f"{type(e).__name__}: {e}"


def _probar() -> int:
    """Envía una notificación de prueba por cada canal configurado."""
    print("Probando canales de notificación configurados…")
    alguno = False
    fallo = False
    if os.getenv("ORO_SMTP_HOST"):
        alguno = True
        ok, err = _probar_email()
        fallo = fallo or not ok
        print(f"  Email    → {'OK, revisa tu bandeja (y la carpeta de spam).' if ok else 'FALLO: ' + err}")
    if os.getenv("ORO_TELEGRAM_TOKEN") and os.getenv("ORO_TELEGRAM_CHAT_ID"):
        alguno = True
        from .notificaciones import NotificadorTelegram
        ok = NotificadorTelegram().enviar("✅ Prueba XAU/USD", "Notificación de prueba. ¡Funciona!")
        fallo = fallo or not ok
        print(f"  Telegram → {'OK' if ok else 'FALLO (revisa token y chat_id).'}")
    if os.getenv("ORO_WEBHOOK_URL"):
        alguno = True
        from .notificaciones import NotificadorWebhook
        ok = NotificadorWebhook().enviar("✅ Prueba XAU/USD", "Notificación de prueba.")
        fallo = fallo or not ok
        print(f"  Webhook  → {'OK' if ok else 'FALLO (revisa la URL).'}")
    if not alguno:
        print("  No hay ningún canal configurado. Define ORO_SMTP_* (email) o ORO_TELEGRAM_* (Telegram).")
        return 1
    return 1 if fallo else 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--probar" in argv:
        return _probar()

    cfg = cargar_configuracion()
    runner = RunnerVivo(
        cfg,
        proveedor=ProveedorYahoo(timeframe=cfg.timeframe),
        notificador=_construir_notificador(),
    )
    ruta = os.getenv("ORO_ESTADO", "oro_estado.json")
    runner.cargar_estado(ruta)
    resultado = runner.ciclo()
    runner.guardar_estado(ruta)

    print(f"[{resultado.momento:%Y-%m-%d %H:%M}] oro={resultado.precio:.2f} | "
          f"{resultado.resumen_sentimiento} | abiertas={resultado.abiertas} "
          f"señales_hoy={resultado.senales_hoy}/{cfg.riesgo.operaciones_max_dia}")
    if resultado.nueva_senal:
        print("→ NUEVA ENTRADA:", resultado.nueva_senal.resumen())
    for ev in resultado.eventos_salida:
        print("→ SALIDA:", ev)
    if not resultado.nueva_senal and not resultado.eventos_salida:
        print("Sin novedades:", resultado.motivo_sin_entrada[:120] or "sin operación A+.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
