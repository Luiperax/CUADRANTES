"""
Arranque de la aplicación gráfica.

Configura la aplicación Qt, aplica el tema oscuro, carga la plantilla de ejemplo
si la base de datos está vacía y muestra la ventana principal.
"""

from __future__ import annotations

import sys

from PySide6 import QtWidgets

from ..datos.datos_iniciales import cargar_plantilla_ejemplo
from ..servicio import ServicioCuadrantes
from .tema import aplicar_tema
from .ventana_principal import VentanaPrincipal


def iniciar(
    ruta_bd: str = "datos/cuadrantes.db",
    lanzar_asistente: bool = False,
    activar_programador: bool = False,
) -> int:
    """Punto de entrada de la interfaz gráfica.

    :param lanzar_asistente: si es ``True``, abre el asistente del mes siguiente
        nada más arrancar (usado por la ejecución automática del día 15).
    :param activar_programador: si es ``True``, activa el programador interno que
        abrirá el asistente automáticamente cada día 15.
    """
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Cuadrantes de Seguridad Privada")
    aplicar_tema(app)

    servicio = ServicioCuadrantes(ruta_bd)
    creados = cargar_plantilla_ejemplo(servicio)
    if creados:
        print(f"Plantilla de ejemplo cargada: {creados} trabajadores.")

    ventana = VentanaPrincipal(servicio)
    ventana.show()

    # Programador interno del día 15 (avisa mientras la aplicación esté abierta).
    if activar_programador:
        from ..programador.planificador import ProgramadorInterno

        def _abrir_asistente(anio: int, mes: int) -> None:
            ventana.combo_mes.setCurrentIndex(mes - 1)
            ventana.spin_anio.setValue(anio)
            ventana.abrir_asistente()

        programador = ProgramadorInterno(_abrir_asistente)
        programador.iniciar()
        app.aboutToQuit.connect(programador.detener)

    if lanzar_asistente:
        # Se difiere para que la ventana esté totalmente visible.
        from PySide6 import QtCore

        QtCore.QTimer.singleShot(300, ventana.abrir_asistente)

    return app.exec()
