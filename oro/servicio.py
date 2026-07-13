"""Servicio de orquestación del sistema de XAU/USD.

Capa fina que coordina proveedor de datos, motor de señales, modelo ML,
notificaciones y backtesting, ofreciendo una API única y sencilla usada tanto
por la línea de comandos como por el servidor web. Aquí no hay lógica de negocio
nueva: solo composición.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import ConfiguracionSistema, cargar_configuracion
from .datos import ProveedorDatos, ProveedorSintetico
from .dominio import MarketSnapshot, sesion_de
from .indicadores import atr as _atr
from .notificaciones import Notificador, NotificadorConsola
from .senales import MotorSenales, ResultadoAnalisis


class ServicioOro:
    def __init__(
        self,
        cfg: Optional[ConfiguracionSistema] = None,
        proveedor: Optional[ProveedorDatos] = None,
        notificador: Optional[Notificador] = None,
        modelo=None,
    ) -> None:
        self.cfg = cfg or cargar_configuracion()
        self.proveedor = proveedor or ProveedorSintetico()
        self.notificador = notificador or NotificadorConsola()
        self.motor = MotorSenales(self.cfg, modelo=modelo)

    # ---- análisis en vivo ----
    def analizar_ahora(self, velas: int = 500) -> ResultadoAnalisis:
        """Analiza el estado de mercado más reciente y devuelve el resultado."""
        df = self.proveedor.historico(velas)
        ultima = df.iloc[-1]
        momento = ultima.name.to_pydatetime()
        atr_val = float(_atr(df, 14).iloc[-1])
        snapshot = MarketSnapshot(
            momento=momento,
            precio=float(ultima["close"]),
            spread=float(ultima.get("spread", 0.25)),
            atr=atr_val,
            sesion=sesion_de(momento),
        )
        return self.motor.analizar(df, snapshot)

    def analizar_y_notificar(self, velas: int = 500) -> ResultadoAnalisis:
        resultado = self.analizar_ahora(velas)
        if resultado.hay_operacion and resultado.signal is not None:
            self.notificador.notificar_senal(resultado.signal)
            self._registrar_senal(resultado.signal)
        return resultado

    def _registrar_senal(self, signal) -> None:
        """Persiste la señal para el aprendizaje continuo (append-only JSONL)."""
        ruta = Path(self.cfg.ruta_operaciones)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        registro = {
            "momento": signal.momento.isoformat(),
            "direccion": signal.direccion.value,
            "entrada": signal.entrada,
            "stop_loss": signal.stop_loss,
            "probabilidad": signal.probabilidad,
            "confianza": signal.confianza,
            "puntuacion": signal.puntuacion,
            "rr": signal.riesgo_recompensa,
        }
        with open(ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")

    # ---- backtesting ----
    def backtest(self, velas: int = 8000):
        from .backtesting import Backtester

        df = self.proveedor.historico(velas)
        return Backtester(self.cfg, self.motor).ejecutar(df)

    # ---- entrenamiento con validación anti-sobreajuste ----
    def entrenar(self, velas: int = 8000, aceptar_si_valido: bool = True) -> dict:
        """Entrena el modelo y valida con walk-forward.

        Solo persiste el modelo si supera la validación fuera de muestra (a menos
        que se fuerce). Devuelve un informe con las métricas de validación.
        """
        from .features import construir_features
        from .ml import ModeloProbabilidad, SKLEARN_DISPONIBLE, generar_etiquetas, walk_forward

        if not SKLEARN_DISPONIBLE:
            return {"error": "scikit-learn no disponible; no se puede entrenar."}

        df = self.proveedor.historico(velas)
        X = construir_features(df)
        y = generar_etiquetas(df, self.cfg)
        wf = walk_forward(X, y)
        informe = {
            "auc_test": wf.auc_test_medio,
            "auc_train": wf.auc_train_medio,
            "brecha_sobreajuste": wf.brecha_sobreajuste,
            "aceptable": wf.aceptable(),
            "resumen": wf.resumen(),
            "guardado": False,
        }
        if wf.aceptable() or not aceptar_si_valido:
            modelo = ModeloProbabilidad().entrenar(X, y)
            modelo.guardar(self.cfg.ruta_modelo)
            self.motor.modelo = modelo
            informe["guardado"] = True
        return informe
