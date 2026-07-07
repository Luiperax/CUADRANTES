"""
Panel de configuración de reglas de negocio.

Todas las reglas de planificación son modificables desde aquí sin tocar el código:
pesos de la optimización, parámetros de descanso, fines de semana, vacaciones y
opciones del solucionador.
"""

from __future__ import annotations

from PySide6 import QtWidgets

from ..config.configuracion import Configuracion


class PanelConfiguracion(QtWidgets.QDialog):
    """Diálogo de edición de la configuración de reglas."""

    def __init__(self, config: Configuracion, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Configuración de reglas")
        self.resize(620, 640)

        disp = QtWidgets.QVBoxLayout(self)
        pestanas = QtWidgets.QTabWidget()
        disp.addWidget(pestanas)

        pestanas.addTab(self._pestana_general(), "General")
        pestanas.addTab(self._pestana_descanso(), "Descansos")
        pestanas.addTab(self._pestana_fines(), "Fines de semana")
        pestanas.addTab(self._pestana_vacaciones(), "Vacaciones")
        pestanas.addTab(self._pestana_pesos(), "Pesos de objetivos")

        botones = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        disp.addWidget(botones)

    # ------------------------------------------------------------------
    def _spin(self, valor, minimo=0, maximo=1000, decimales=0):
        if decimales:
            w = QtWidgets.QDoubleSpinBox()
            w.setDecimals(decimales)
        else:
            w = QtWidgets.QSpinBox()
        w.setRange(minimo, maximo)
        w.setValue(valor)
        return w

    def _check(self, valor):
        w = QtWidgets.QCheckBox()
        w.setChecked(valor)
        return w

    def _pestana_general(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(w)
        self.w_empresa = QtWidgets.QLineEdit(self.config.empresa)
        self.w_sede = QtWidgets.QLineEdit(self.config.sede)
        self.w_cm = self._spin(self.config.computo_mensual_referencia, 0, 400, 2)
        self.w_tiempo = self._spin(self.config.tiempo_maximo_solver_segundos, 5, 600)
        self.w_meses = self._spin(self.config.meses_historico_considerados, 0, 60)
        self.w_horas_ausencia = self._spin(
            self.config.horas_computo_por_dia_ausencia, 0, 24, decimales=2)
        f.addRow("Empresa:", self.w_empresa)
        f.addRow("Sede:", self.w_sede)
        f.addRow("Cómputo mensual (C.M.):", self.w_cm)
        f.addRow("Horas por día de vacaciones/permiso:", self.w_horas_ausencia)
        f.addRow("Tiempo máx. solucionador (s):", self.w_tiempo)
        f.addRow("Meses de histórico considerados:", self.w_meses)
        return w

    def _pestana_descanso(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(w)
        d = self.config.descanso
        self.w_max_dias = self._spin(d.max_dias_consecutivos, 1, 15)
        self.w_max_noches = self._spin(d.max_noches_consecutivas, 1, 10)
        self.w_pen_noche_man = self._check(d.penalizar_noche_tras_manana)
        self.w_libres_noche = self._spin(d.dias_libres_tras_noches, 0, 5)
        f.addRow("Máx. días consecutivos:", self.w_max_dias)
        f.addRow("Máx. noches consecutivas:", self.w_max_noches)
        f.addRow("Penalizar noche tras mañana:", self.w_pen_noche_man)
        f.addRow("Días libres tras bloque de noches:", self.w_libres_noche)
        return w

    def _pestana_fines(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(w)
        fs = self.config.fin_de_semana
        self.w_sd_mismo = self._check(fs.sabado_domingo_mismo_trabajador)
        self.w_fs_min = self._spin(fs.fines_semana_objetivo_min, 0, 5)
        self.w_fs_max = self._spin(fs.fines_semana_objetivo_max, 0, 5)
        self.w_fs_tope = self._spin(fs.fines_semana_tope_duro, 1, 5)
        f.addRow("Sábado y domingo mismo trabajador:", self.w_sd_mismo)
        f.addRow("Fines de semana objetivo (mín.):", self.w_fs_min)
        f.addRow("Fines de semana objetivo (máx.):", self.w_fs_max)
        f.addRow("Tope de fines de semana:", self.w_fs_tope)
        return w

    def _pestana_vacaciones(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(w)
        v = self.config.vacaciones
        self.w_antes_min = self._spin(v.dias_libres_antes_min, 0, 10)
        self.w_antes_max = self._spin(v.dias_libres_antes_max, 0, 10)
        self.w_desp_min = self._spin(v.dias_libres_despues_min, 0, 10)
        self.w_desp_max = self._spin(v.dias_libres_despues_max, 0, 10)
        self.w_ev_antes = self._check(v.evitar_noche_antes)
        self.w_ev_reinc = self._check(v.evitar_noche_al_reincorporarse)
        f.addRow("Días libres antes (mín.):", self.w_antes_min)
        f.addRow("Días libres antes (máx.):", self.w_antes_max)
        f.addRow("Días libres después (mín.):", self.w_desp_min)
        f.addRow("Días libres después (máx.):", self.w_desp_max)
        f.addRow("Evitar noche antes de vacaciones:", self.w_ev_antes)
        f.addRow("Evitar noche al reincorporarse:", self.w_ev_reinc)
        return w

    def _pestana_pesos(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(w)
        p = self.config.pesos
        self.w_pesos = {}
        etiquetas = {
            "equilibrio_horas": "Equilibrio de horas",
            "equilibrio_horas_extra": "Equilibrio de horas extra",
            "equilibrio_noches": "Equilibrio de noches",
            "equilibrio_fines_semana": "Equilibrio de fines de semana",
            "equilibrio_festivos": "Equilibrio de festivos (anual)",
            "rotacion_puestos": "Rotación de puestos",
            "respetar_preferencias": "Respetar preferencias",
            "agrupar_descansos": "Agrupar descansos",
            "recuperacion_tras_noche": "Recuperación tras noche",
            "evitar_cambios_bruscos": "Evitar cambios bruscos",
            "adaptacion_vacaciones": "Adaptación de vacaciones",
            "tener_en_cuenta_historico": "Peso de la memoria histórica",
        }
        for clave, etiqueta in etiquetas.items():
            spin = self._spin(getattr(p, clave), 0, 1000)
            self.w_pesos[clave] = spin
            f.addRow(etiqueta + ":", spin)
        return w

    # ------------------------------------------------------------------
    def configuracion_resultante(self) -> Configuracion:
        c = self.config
        c.empresa = self.w_empresa.text()
        c.sede = self.w_sede.text()
        c.computo_mensual_referencia = self.w_cm.value()
        c.tiempo_maximo_solver_segundos = self.w_tiempo.value()
        c.meses_historico_considerados = self.w_meses.value()
        c.horas_computo_por_dia_ausencia = self.w_horas_ausencia.value()

        c.descanso.max_dias_consecutivos = self.w_max_dias.value()
        c.descanso.max_noches_consecutivas = self.w_max_noches.value()
        c.descanso.penalizar_noche_tras_manana = self.w_pen_noche_man.isChecked()
        c.descanso.dias_libres_tras_noches = self.w_libres_noche.value()

        c.fin_de_semana.sabado_domingo_mismo_trabajador = self.w_sd_mismo.isChecked()
        c.fin_de_semana.fines_semana_objetivo_min = self.w_fs_min.value()
        c.fin_de_semana.fines_semana_objetivo_max = self.w_fs_max.value()
        c.fin_de_semana.fines_semana_tope_duro = self.w_fs_tope.value()

        c.vacaciones.dias_libres_antes_min = self.w_antes_min.value()
        c.vacaciones.dias_libres_antes_max = self.w_antes_max.value()
        c.vacaciones.dias_libres_despues_min = self.w_desp_min.value()
        c.vacaciones.dias_libres_despues_max = self.w_desp_max.value()
        c.vacaciones.evitar_noche_antes = self.w_ev_antes.isChecked()
        c.vacaciones.evitar_noche_al_reincorporarse = self.w_ev_reinc.isChecked()

        for clave, spin in self.w_pesos.items():
            setattr(c.pesos, clave, spin.value())
        return c
