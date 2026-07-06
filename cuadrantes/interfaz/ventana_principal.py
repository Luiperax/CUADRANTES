"""
Ventana principal de la aplicación.

Integra todos los componentes en una interfaz moderna en modo oscuro: barra de
herramientas, panel lateral con el histórico de cuadrantes, calendario mensual
editable, pestañas de auditoría y estadísticas, buscador, filtros e indicadores.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..config.constantes import NOMBRES_MES, EstadoCuadrante
from ..servicio import ServicioCuadrantes
from ..validacion.auditoria import EstadoRegla
from .asistente import AsistenteCuadrante
from .gestor_trabajadores import GestorTrabajadores
from .graficos import GraficoBarras
from .panel_configuracion import PanelConfiguracion
from .tema import PaletaOscura
from .vista_calendario import VistaCalendario


class VentanaPrincipal(QtWidgets.QMainWindow):
    """Ventana principal del generador de cuadrantes."""

    def __init__(self, servicio: ServicioCuadrantes):
        super().__init__()
        self.servicio = servicio
        self.cuadrante_actual = None
        self.setWindowTitle("Generador de Cuadrantes de Seguridad Privada")
        self.resize(1360, 800)

        self._crear_barra_herramientas()
        self._crear_cuerpo()
        self._crear_barra_estado()
        self.recargar_historico()

    # ------------------------------------------------------------------
    def _crear_barra_herramientas(self) -> None:
        barra = self.addToolBar("Principal")
        barra.setMovable(False)
        barra.setIconSize(QtCore.QSize(18, 18))

        def accion(texto, funcion):
            act = QtGui.QAction(texto, self)
            act.triggered.connect(funcion)
            barra.addAction(act)
            return act

        accion("🗓️  Generar cuadrante", self.abrir_asistente)
        barra.addSeparator()
        accion("📊  Exportar Excel", self.exportar_excel)
        accion("📄  Exportar PDF", self.exportar_pdf)
        accion("📋  Informes", self.exportar_informes)
        barra.addSeparator()
        accion("👥  Trabajadores", self.gestionar_trabajadores)
        accion("⚙️  Configuración", self.abrir_configuracion)
        accion("💾  Copia de seguridad", self.copia_seguridad)

    def _crear_cuerpo(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        disposicion = QtWidgets.QHBoxLayout(central)
        disposicion.setContentsMargins(0, 0, 0, 0)

        # --- Panel lateral ---
        panel = QtWidgets.QWidget()
        panel.setObjectName("panelLateral")
        panel.setFixedWidth(260)
        pl = QtWidgets.QVBoxLayout(panel)

        pl.addWidget(self._etiqueta("Nuevo cuadrante", "titulo"))
        sel = QtWidgets.QHBoxLayout()
        self.combo_mes = QtWidgets.QComboBox()
        for i in range(1, 13):
            self.combo_mes.addItem(NOMBRES_MES[i].capitalize(), i)
        self.spin_anio = QtWidgets.QSpinBox()
        self.spin_anio.setRange(2020, 2100)
        hoy = date.today()
        mes_sig = hoy.month % 12 + 1
        anio_sig = hoy.year + (1 if hoy.month == 12 else 0)
        self.combo_mes.setCurrentIndex(mes_sig - 1)
        self.spin_anio.setValue(anio_sig)
        sel.addWidget(self.combo_mes)
        sel.addWidget(self.spin_anio)
        pl.addLayout(sel)
        boton_generar = QtWidgets.QPushButton("Generar con asistente")
        boton_generar.setObjectName("primario")
        boton_generar.clicked.connect(self.abrir_asistente)
        pl.addWidget(boton_generar)

        pl.addWidget(self._etiqueta("Histórico de cuadrantes", "subtitulo"))
        self.lista_historico = QtWidgets.QListWidget()
        self.lista_historico.itemClicked.connect(self._seleccionar_historico)
        pl.addWidget(self.lista_historico)
        disposicion.addWidget(panel)

        # --- Zona central ---
        derecha = QtWidgets.QVBoxLayout()
        cabecera = QtWidgets.QHBoxLayout()
        self.etiqueta_titulo = self._etiqueta("Seleccione o genere un cuadrante", "titulo")
        cabecera.addWidget(self.etiqueta_titulo)
        cabecera.addStretch()
        cabecera.addWidget(QtWidgets.QLabel("🔎 Buscar:"))
        self.buscador = QtWidgets.QLineEdit()
        self.buscador.setPlaceholderText("Filtrar por trabajador…")
        self.buscador.setFixedWidth(220)
        self.buscador.textChanged.connect(self._filtrar)
        cabecera.addWidget(self.buscador)
        derecha.addLayout(cabecera)

        self.pestanas = QtWidgets.QTabWidget()
        self.vista_calendario = VistaCalendario(self.servicio.mapa_trabajadores())
        self.vista_calendario.cuadrante_modificado.connect(self._al_modificar)
        self.pestanas.addTab(self.vista_calendario, "📅 Calendario")

        self.tabla_auditoria = QtWidgets.QTableWidget(0, 4)
        self.tabla_auditoria.setHorizontalHeaderLabels(
            ["Regla", "Estado", "Motivo", "Solución propuesta"])
        self.tabla_auditoria.horizontalHeader().setStretchLastSection(True)
        self.pestanas.addTab(self.tabla_auditoria, "✅ Auditoría")

        self.panel_estadisticas = self._crear_panel_estadisticas()
        self.pestanas.addTab(self.panel_estadisticas, "📈 Estadísticas")
        derecha.addWidget(self.pestanas)
        disposicion.addLayout(derecha)

    def _crear_panel_estadisticas(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        disp = QtWidgets.QVBoxLayout(w)
        self.resumen_general = self._etiqueta("", "subtitulo")
        disp.addWidget(self.resumen_general)
        self.grafico_horas = GraficoBarras("Horas trabajadas por trabajador")
        self.grafico_noches = GraficoBarras("Noches por trabajador")
        self.grafico_findes = GraficoBarras("Fines de semana por trabajador")
        disp.addWidget(self.grafico_horas)
        disp.addWidget(self.grafico_noches)
        disp.addWidget(self.grafico_findes)
        return w

    def _crear_barra_estado(self) -> None:
        self.barra_estado = self.statusBar()
        self.indicador = QtWidgets.QLabel("Listo")
        self.barra_estado.addPermanentWidget(self.indicador)

    def _etiqueta(self, texto, objeto) -> QtWidgets.QLabel:
        etiqueta = QtWidgets.QLabel(texto)
        etiqueta.setObjectName(objeto)
        return etiqueta

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def abrir_asistente(self) -> None:
        anio = self.spin_anio.value()
        mes = self.combo_mes.currentData()
        asistente = AsistenteCuadrante(self.servicio, anio, mes, self)
        if asistente.exec() == QtWidgets.QWizard.Accepted:
            asistente.guardar_datos()
            self._generar(anio, mes)

    def _generar(self, anio: int, mes: int) -> None:
        self.indicador.setText("Generando cuadrante… (optimización en curso)")
        QtWidgets.QApplication.processEvents()
        try:
            resultado = self.servicio.generar(anio, mes)
        except Exception as exc:  # pragma: no cover - protección de la interfaz
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo generar: {exc}")
            self.indicador.setText("Error en la generación")
            return
        self.cuadrante_actual = resultado.cuadrante
        self._mostrar_cuadrante(resultado.cuadrante)
        self.recargar_historico()
        mensaje = (f"Generado en {resultado.tiempo_segundos:.1f}s — "
                   f"{resultado.cuadrante.estado.descripcion}")
        if resultado.puestos_sin_cubrir:
            mensaje += f" — {len(resultado.puestos_sin_cubrir)} puesto(s) sin cubrir"
        self.indicador.setText(mensaje)

    def _mostrar_cuadrante(self, cuadrante) -> None:
        self.vista_calendario.trabajadores = self.servicio.mapa_trabajadores()
        self.vista_calendario.cargar(cuadrante)
        self.etiqueta_titulo.setText(
            f"{NOMBRES_MES[cuadrante.mes]} {cuadrante.anio} · v{cuadrante.version} · "
            f"{cuadrante.estado.descripcion}")
        self._actualizar_auditoria()
        self._actualizar_estadisticas()

    def _actualizar_auditoria(self) -> None:
        if not self.cuadrante_actual:
            return
        informe = self.servicio.auditar(self.cuadrante_actual)
        self.tabla_auditoria.setRowCount(len(informe.reglas))
        colores = {
            EstadoRegla.CUMPLE: PaletaOscura.EXITO,
            EstadoRegla.ADVERTENCIA: PaletaOscura.ADVERTENCIA,
            EstadoRegla.NO_CUMPLE: PaletaOscura.ERROR,
        }
        for i, regla in enumerate(informe.reglas):
            self.tabla_auditoria.setItem(i, 0, QtWidgets.QTableWidgetItem(regla.nombre))
            item_estado = QtWidgets.QTableWidgetItem(regla.estado.value)
            item_estado.setForeground(QtGui.QColor(colores[regla.estado]))
            self.tabla_auditoria.setItem(i, 1, item_estado)
            self.tabla_auditoria.setItem(i, 2, QtWidgets.QTableWidgetItem(regla.motivo))
            self.tabla_auditoria.setItem(i, 3, QtWidgets.QTableWidgetItem(regla.solucion_propuesta))
        self.tabla_auditoria.resizeColumnsToContents()

    def _actualizar_estadisticas(self) -> None:
        from ..dominio.computos import calcular_resumenes

        cuad = self.cuadrante_actual
        trabajadores = self.servicio.mapa_trabajadores()
        resumenes = calcular_resumenes(cuad, trabajadores)
        ids = cuad.trabajadores_ids or list(trabajadores.keys())

        def nombre(tid):
            return trabajadores[tid].nombre if tid in trabajadores else str(tid)

        self.grafico_horas.establecer_datos(
            [(nombre(t), resumenes[t].horas_trabajadas) for t in ids if t in resumenes],
            PaletaOscura.ACENTO)
        self.grafico_noches.establecer_datos(
            [(nombre(t), resumenes[t].numero_noches) for t in ids if t in resumenes],
            PaletaOscura.NOCHE)
        self.grafico_findes.establecer_datos(
            [(nombre(t), resumenes[t].numero_fines_semana) for t in ids if t in resumenes],
            PaletaOscura.ADVERTENCIA)

        total_horas = sum(r.horas_trabajadas for r in resumenes.values())
        self.resumen_general.setText(
            f"Total de horas del servicio: {total_horas:.0f} h  ·  "
            f"Trabajadores: {len(ids)}  ·  Estado: {cuad.estado.descripcion}")

    def _al_modificar(self) -> None:
        """Se ejecuta tras una edición manual: recalcula y revalida."""
        if self.cuadrante_actual:
            self.cuadrante_actual.estado = EstadoCuadrante.BORRADOR
            self.servicio.cuadrantes.guardar(self.cuadrante_actual)  # Autoguardado.
            informe = self.servicio.auditar(self.cuadrante_actual)
            self.cuadrante_actual.estado = informe.estado_cuadrante
            self._actualizar_auditoria()
            self._actualizar_estadisticas()
            self.indicador.setText(
                f"Cambio aplicado y revalidado — {informe.estado_cuadrante.descripcion} (autoguardado)")

    def _filtrar(self, texto: str) -> None:
        self.vista_calendario.aplicar_filtro(texto)

    # ------------------------------------------------------------------
    def recargar_historico(self) -> None:
        self.lista_historico.clear()
        for cab in self.servicio.cuadrantes.listar_cabeceras():
            estado = EstadoCuadrante(cab["estado"]).descripcion
            texto = f"{NOMBRES_MES[cab['mes']].capitalize()} {cab['anio']} · v{cab['version']}"
            item = QtWidgets.QListWidgetItem(f"{texto}\n{estado}")
            item.setData(256, cab["id"])
            self.lista_historico.addItem(item)

    def _seleccionar_historico(self, item) -> None:
        cuadrante_id = item.data(256)
        cuadrante = self.servicio.cuadrantes.cargar(cuadrante_id)
        if cuadrante:
            self.cuadrante_actual = cuadrante
            self._mostrar_cuadrante(cuadrante)

    def gestionar_trabajadores(self) -> None:
        GestorTrabajadores(self.servicio, self).exec()
        self.vista_calendario.trabajadores = self.servicio.mapa_trabajadores()

    def abrir_configuracion(self) -> None:
        panel = PanelConfiguracion(self.servicio.configuracion(), self)
        if panel.exec() == QtWidgets.QDialog.Accepted:
            self.servicio.guardar_configuracion(panel.configuracion_resultante())
            self.indicador.setText("Configuración guardada")

    # ------------------------------------------------------------------
    def _pedir_ruta(self, titulo, filtro, sufijo) -> Path | None:
        if not self.cuadrante_actual:
            QtWidgets.QMessageBox.information(self, "Aviso", "Genere o seleccione un cuadrante primero.")
            return None
        nombre = f"Cuadrante_{NOMBRES_MES[self.cuadrante_actual.mes]}_{self.cuadrante_actual.anio}{sufijo}"
        ruta, _ = QtWidgets.QFileDialog.getSaveFileName(self, titulo, nombre, filtro)
        return Path(ruta) if ruta else None

    def exportar_excel(self) -> None:
        ruta = self._pedir_ruta("Exportar a Excel", "Excel (*.xlsx)", ".xlsx")
        if ruta:
            self.servicio.exportar_excel(self.cuadrante_actual, ruta)
            self.indicador.setText(f"Excel exportado: {ruta.name}")

    def exportar_pdf(self) -> None:
        ruta = self._pedir_ruta("Exportar a PDF", "PDF (*.pdf)", ".pdf")
        if ruta:
            self.servicio.exportar_pdf(self.cuadrante_actual, ruta)
            self.indicador.setText(f"PDF exportado: {ruta.name}")

    def exportar_informes(self) -> None:
        ruta = self._pedir_ruta("Exportar informes", "PDF (*.pdf)", "_informes.pdf")
        if ruta:
            self.servicio.exportar_informes(self.cuadrante_actual, ruta)
            self.indicador.setText(f"Informes exportados: {ruta.name}")

    def copia_seguridad(self) -> None:
        ruta = self.servicio.copia_seguridad()
        QtWidgets.QMessageBox.information(self, "Copia de seguridad",
                                          f"Copia creada en:\n{ruta}")
