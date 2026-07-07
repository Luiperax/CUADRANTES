"""
Capa de servicio: orquesta el flujo completo de generación de cuadrantes.

Es el punto de entrada de alto nivel que utilizan tanto la interfaz gráfica como
el programador automático. Coordina base de datos, motor de optimización,
auditoría, exportación e informes, ocultando la complejidad de cada subsistema.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .config.configuracion import Configuracion
from .datos.base_datos import BaseDatos
from .datos.modelos import Cuadrante, Trabajador
from .datos.repositorios import (
    RepositorioAusencias,
    RepositorioConfiguracion,
    RepositorioCuadrantes,
    RepositorioFestivos,
    RepositorioIncidencias,
    RepositorioRestricciones,
    RepositorioTrabajadores,
)
from .dominio.historico import AgregadorHistorico
from .exportacion.excel import ExportadorExcel
from .exportacion.pdf import ExportadorPDF
from .informes.generador import GeneradorInformes
from .motor.optimizador import OptimizadorCuadrante, ResultadoOptimizacion
from .validacion.auditoria import Auditor, InformeAuditoria


class ServicioCuadrantes:
    """Fachada principal de la aplicación."""

    def __init__(self, ruta_bd: str | Path = "datos/cuadrantes.db"):
        self.bd = BaseDatos(ruta_bd)
        self.trabajadores = RepositorioTrabajadores(self.bd)
        self.ausencias = RepositorioAusencias(self.bd)
        self.restricciones = RepositorioRestricciones(self.bd)
        self.festivos = RepositorioFestivos(self.bd)
        self.incidencias = RepositorioIncidencias(self.bd)
        self.cuadrantes = RepositorioCuadrantes(self.bd)
        self.config_repo = RepositorioConfiguracion(self.bd)

    # ------------------------------------------------------------------
    def configuracion(self) -> Configuracion:
        return self.config_repo.cargar()

    def guardar_configuracion(self, config: Configuracion) -> None:
        self.config_repo.guardar(config)

    def mapa_trabajadores(self) -> dict[int, Trabajador]:
        return {t.id: t for t in self.trabajadores.listar()}

    # ------------------------------------------------------------------
    def generar(self, anio: int, mes: int, guardar: bool = True) -> ResultadoOptimizacion:
        """Genera el cuadrante de un mes teniendo en cuenta el histórico.

        Reúne toda la información necesaria (plantilla activa, ausencias,
        restricciones, festivos e histórico), ejecuta el motor de optimización y,
        opcionalmente, persiste el resultado.
        """
        config = self.configuracion()
        trabajadores = self.trabajadores.listar(solo_activos=True)
        ausencias = self.ausencias.listar_por_mes(anio, mes)
        restricciones = self.restricciones.listar_por_mes(anio, mes)
        festivos = {f.fecha for f in self.festivos.listar_por_mes(anio, mes)}

        # Memoria histórica de los meses anteriores.
        previos = self.cuadrantes.cargar_historico(anio, mes, config.meses_historico_considerados)
        carga = AgregadorHistorico(previos).calcular()

        optimizador = OptimizadorCuadrante(
            anio=anio, mes=mes, trabajadores=trabajadores, configuracion=config,
            ausencias=ausencias, restricciones=restricciones, festivos=festivos,
            carga_historica=carga,
        )
        resultado = optimizador.resolver()

        # Aplicar el estado según la auditoría.
        informe = self.auditar(resultado.cuadrante)
        resultado.cuadrante.estado = informe.estado_cuadrante

        if guardar:
            # Versionado: si ya existe un cuadrante del mes, se crea nueva versión.
            existente = self.cuadrantes.ultima_version(anio, mes)
            if existente:
                resultado.cuadrante.version = existente.version + 1
            self.cuadrantes.guardar(resultado.cuadrante)
        return resultado

    def auditar(self, cuadrante: Cuadrante) -> InformeAuditoria:
        config = self.configuracion()
        trabajadores = self.mapa_trabajadores()
        ausencias = self.ausencias.listar_por_mes(cuadrante.anio, cuadrante.mes)
        return Auditor(cuadrante, trabajadores, config, ausencias).auditar()

    # ------------------------------------------------------------------
    def exportar_excel(self, cuadrante: Cuadrante, ruta: str | Path) -> Path:
        return ExportadorExcel(cuadrante, self.mapa_trabajadores()).exportar(ruta)

    def exportar_pdf(self, cuadrante: Cuadrante, ruta: str | Path) -> Path:
        return ExportadorPDF(cuadrante, self.mapa_trabajadores()).exportar(ruta)

    def exportar_informes(self, cuadrante: Cuadrante, ruta: str | Path) -> Path:
        ausencias = self.ausencias.listar_por_mes(cuadrante.anio, cuadrante.mes)
        incidencias = self.incidencias.listar_por_mes(cuadrante.anio, cuadrante.mes)
        generador = GeneradorInformes(
            cuadrante, self.mapa_trabajadores(), self.configuracion(), ausencias, incidencias
        )
        return generador.exportar_pdf(ruta)

    def eliminar_cuadrante(self, cuadrante_id: int) -> None:
        """Elimina un cuadrante del historial (por ejemplo, si salió mal)."""
        self.cuadrantes.eliminar(cuadrante_id)

    def copia_seguridad(self) -> Path:
        return self.bd.copia_seguridad()

    # ------------------------------------------------------------------
    def cerrar(self) -> None:
        self.bd.cerrar()
