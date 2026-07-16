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
    def asegurar_festivos_oficiales(self, anio: int) -> int:
        """Carga los festivos oficiales del año para la comunidad/municipio configurados.

        Solo actúa si ese año no tiene ningún festivo registrado, de modo que no
        pisa los festivos que el usuario haya podido personalizar. Por defecto usa
        el calendario de la Comunidad de Madrid y Madrid capital.

        :return: número de festivos añadidos (0 si ya había festivos ese año).
        """
        from .datos.modelos import Festivo
        from .dominio.festivos_espana import festivos_del_anio

        ya_registrados = [
            f for f in self.festivos.listar_todos() if f.fecha.year == anio
        ]
        if ya_registrados:
            return 0

        config = self.configuracion()
        anadidos = 0
        for fecha, descripcion in festivos_del_anio(anio, config.comunidad_autonoma, config.municipio):
            self.festivos.guardar(Festivo(id=None, fecha=fecha, descripcion=descripcion))
            anadidos += 1
        return anadidos

    def cargar_festivos_oficiales(self, anio: int) -> int:
        """Carga (o actualiza) los festivos oficiales del año indicado.

        A diferencia de :meth:`asegurar_festivos_oficiales`, esta versión siempre
        inserta el calendario oficial de la comunidad/municipio configurados
        (sobrescribiendo por fecha), pensada para el botón «Cargar festivos» del
        gestor. Los festivos personalizados en otras fechas se conservan.

        :return: número de festivos del calendario oficial cargados.
        """
        from .datos.modelos import Festivo
        from .dominio.festivos_espana import festivos_del_anio

        config = self.configuracion()
        cargados = 0
        for fecha, descripcion in festivos_del_anio(anio, config.comunidad_autonoma, config.municipio):
            self.festivos.guardar(Festivo(id=None, fecha=fecha, descripcion=descripcion))
            cargados += 1
        return cargados

    def generar(self, anio: int, mes: int, guardar: bool = True) -> ResultadoOptimizacion:
        """Genera el cuadrante de un mes teniendo en cuenta el histórico.

        Reúne toda la información necesaria (plantilla activa, ausencias,
        restricciones, festivos e histórico), ejecuta el motor de optimización y,
        opcionalmente, persiste el resultado.
        """
        config = self.configuracion()
        # Asegura los festivos oficiales del año (Madrid por defecto) y del año
        # anterior, para que el mes y el histórico consideren los festivos correctos.
        self.asegurar_festivos_oficiales(anio)
        self.asegurar_festivos_oficiales(anio - 1)
        trabajadores = self.trabajadores.listar(solo_activos=True)
        ausencias = self.ausencias.listar_por_mes(anio, mes)
        restricciones = self.restricciones.listar_por_mes(anio, mes)
        festivos = {f.fecha for f in self.festivos.listar_por_mes(anio, mes)}

        # Memoria histórica de los meses anteriores. Se aportan los festivos de cada
        # mes para contar correctamente quién ha trabajado los festivos del año.
        previos = self.cuadrantes.cargar_historico(anio, mes, config.meses_historico_considerados)
        festivos_por_mes = self.festivos.mapa_por_mes()
        carga = AgregadorHistorico(previos, festivos_por_mes).calcular()

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

    def festivos_del_mes(self, anio: int, mes: int) -> set[date]:
        """Fechas festivas del mes, para contar los festivos trabajados y auditar
        el equilibrio anual de festivos correctamente."""
        return {f.fecha for f in self.festivos.listar_por_mes(anio, mes)}

    def auditar(self, cuadrante: Cuadrante) -> InformeAuditoria:
        config = self.configuracion()
        trabajadores = self.mapa_trabajadores()
        ausencias = self.ausencias.listar_por_mes(cuadrante.anio, cuadrante.mes)
        festivos = self.festivos_del_mes(cuadrante.anio, cuadrante.mes)
        return Auditor(cuadrante, trabajadores, config, ausencias, festivos=festivos).auditar()

    # ------------------------------------------------------------------
    def exportar_excel(self, cuadrante: Cuadrante, ruta: str | Path) -> Path:
        festivos = self.festivos_del_mes(cuadrante.anio, cuadrante.mes)
        return ExportadorExcel(cuadrante, self.mapa_trabajadores(), festivos=festivos).exportar(ruta)

    def exportar_pdf(self, cuadrante: Cuadrante, ruta: str | Path) -> Path:
        festivos = self.festivos_del_mes(cuadrante.anio, cuadrante.mes)
        return ExportadorPDF(cuadrante, self.mapa_trabajadores(), festivos=festivos).exportar(ruta)

    def exportar_facturacion(self, cuadrante: Cuadrante, ruta: str | Path) -> Path:
        """Exporta el cuadrante de FACTURACIÓN (formato del cliente, por servicio).

        Se incluyen todos los trabajadores que cubrieron algún servicio ese mes
        (también los eventuales), porque la facturación refleja el servicio real."""
        from .exportacion.facturacion import ExportadorFacturacion
        festivos = self.festivos_del_mes(cuadrante.anio, cuadrante.mes)
        trab = {t.id: t for t in self.trabajadores.listar()}  # todos, no solo activos
        return ExportadorFacturacion(cuadrante, trab, festivos=festivos).exportar(ruta)

    def exportar_facturacion_pdf(self, cuadrante: Cuadrante, ruta: str | Path) -> Path:
        """Exporta el cuadrante de facturación a PDF (mismo contenido que el Excel)."""
        from .exportacion.facturacion import ExportadorFacturacionPDF
        festivos = self.festivos_del_mes(cuadrante.anio, cuadrante.mes)
        trab = {t.id: t for t in self.trabajadores.listar()}
        return ExportadorFacturacionPDF(cuadrante, trab, festivos=festivos).exportar(ruta)

    def exportar_informes(self, cuadrante: Cuadrante, ruta: str | Path) -> Path:
        ausencias = self.ausencias.listar_por_mes(cuadrante.anio, cuadrante.mes)
        incidencias = self.incidencias.listar_por_mes(cuadrante.anio, cuadrante.mes)
        festivos = {f.fecha for f in self.festivos.listar_por_mes(cuadrante.anio, cuadrante.mes)}
        generador = GeneradorInformes(
            cuadrante, self.mapa_trabajadores(), self.configuracion(), ausencias,
            incidencias, festivos=festivos
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
