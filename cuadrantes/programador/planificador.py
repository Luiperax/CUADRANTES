"""
Programador de ejecución automática (día 15 de cada mes).

Según el pliego, la aplicación debe ejecutarse automáticamente cada día 15 para
preparar el cuadrante del mes siguiente, pero SIN generar nada sin preguntar
antes: se limita a lanzar el asistente previo.

Se ofrecen dos mecanismos complementarios:

1. :class:`ProgramadorInterno` — basado en APScheduler. Mientras la aplicación
   esté abierta, dispara una señal el día 15 para abrir el asistente.
2. :func:`generar_tarea_windows` — genera el comando para registrar una tarea en
   el «Programador de tareas de Windows», útil si se desea que el sistema abra la
   aplicación automáticamente aunque no esté en ejecución.
"""

from __future__ import annotations

from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class ProgramadorInterno:
    """Programador en segundo plano que avisa el día 15 de cada mes."""

    def __init__(self, callback_dia_15):
        """
        :param callback_dia_15: función a ejecutar el día 15 (por ejemplo, abrir
            el asistente para el mes siguiente).
        """
        self.callback = callback_dia_15
        self.scheduler = BackgroundScheduler()

    def iniciar(self, hora: int = 9, minuto: int = 0) -> None:
        """Programa la ejecución para las ``hora:minuto`` del día 15."""
        self.scheduler.add_job(
            self._disparar,
            CronTrigger(day=15, hour=hora, minute=minuto),
            id="generacion_mensual",
            replace_existing=True,
        )
        self.scheduler.start()

    def _disparar(self) -> None:
        proximo = _mes_siguiente(date.today())
        self.callback(proximo[0], proximo[1])

    def detener(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)


def _mes_siguiente(hoy: date) -> tuple[int, int]:
    """Devuelve (año, mes) del mes siguiente al de ``hoy``."""
    if hoy.month == 12:
        return hoy.year + 1, 1
    return hoy.year, hoy.month + 1


def generar_tarea_windows(ruta_python: str, ruta_script: str) -> str:
    """Devuelve el comando ``schtasks`` para registrar la tarea en Windows.

    El usuario puede ejecutar este comando (una sola vez, como administrador) para
    que Windows abra la aplicación cada día 15 a las 09:00.
    """
    return (
        'schtasks /Create /SC MONTHLY /D 15 /TN "GeneradorCuadrantes" '
        f'/TR "\\"{ruta_python}\\" \\"{ruta_script}\\" --asistente" /ST 09:00 /F'
    )
