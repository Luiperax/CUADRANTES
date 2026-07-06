"""
Tema visual oscuro y profesional para la interfaz gráfica.

Define una hoja de estilos (QSS) coherente y una paleta de colores que confiere a
la aplicación un aspecto moderno en modo oscuro, como exige el pliego.
"""

from __future__ import annotations


class PaletaOscura:
    """Colores base del tema oscuro."""

    FONDO = "#1e1f26"
    FONDO_PANEL = "#262832"
    FONDO_ELEMENTO = "#2f313d"
    BORDE = "#3a3d4a"
    TEXTO = "#e6e6ea"
    TEXTO_TENUE = "#9aa0ad"
    ACENTO = "#4c8bf5"          # Azul principal.
    ACENTO_OSCURO = "#2f5fb0"
    EXITO = "#3ecf8e"           # Verde (validado / cumple).
    ADVERTENCIA = "#f5a623"     # Naranja (advertencia).
    ERROR = "#e0575b"           # Rojo (no cumple).
    NOCHE = "#00b0f0"           # Cian (turno de noche).
    FIN_SEMANA = "#4a4632"      # Fondo tenue para fines de semana.
    VACACIONES = "#b8860b"


HOJA_ESTILOS = f"""
* {{
    font-family: "Segoe UI", "Noto Sans", Arial, sans-serif;
    font-size: 13px;
    color: {PaletaOscura.TEXTO};
}}
QMainWindow, QDialog, QWizard {{
    background-color: {PaletaOscura.FONDO};
}}
QWidget#panelLateral {{
    background-color: {PaletaOscura.FONDO_PANEL};
    border-right: 1px solid {PaletaOscura.BORDE};
}}
QLabel#titulo {{
    font-size: 20px;
    font-weight: bold;
    color: {PaletaOscura.TEXTO};
}}
QLabel#subtitulo {{
    color: {PaletaOscura.TEXTO_TENUE};
}}
QPushButton {{
    background-color: {PaletaOscura.FONDO_ELEMENTO};
    border: 1px solid {PaletaOscura.BORDE};
    border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background-color: {PaletaOscura.BORDE};
}}
QPushButton#primario {{
    background-color: {PaletaOscura.ACENTO};
    border: none;
    color: white;
    font-weight: bold;
}}
QPushButton#primario:hover {{
    background-color: {PaletaOscura.ACENTO_OSCURO};
}}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: {PaletaOscura.FONDO_ELEMENTO};
    border: 1px solid {PaletaOscura.BORDE};
    border-radius: 5px;
    padding: 5px;
}}
QTableWidget, QTableView, QTreeWidget, QListWidget {{
    background-color: {PaletaOscura.FONDO_PANEL};
    gridline-color: {PaletaOscura.BORDE};
    border: 1px solid {PaletaOscura.BORDE};
    selection-background-color: {PaletaOscura.ACENTO_OSCURO};
}}
QHeaderView::section {{
    background-color: {PaletaOscura.FONDO_ELEMENTO};
    padding: 4px;
    border: 1px solid {PaletaOscura.BORDE};
    font-weight: bold;
}}
QTabWidget::pane {{
    border: 1px solid {PaletaOscura.BORDE};
}}
QTabBar::tab {{
    background-color: {PaletaOscura.FONDO_PANEL};
    padding: 8px 16px;
    border: 1px solid {PaletaOscura.BORDE};
}}
QTabBar::tab:selected {{
    background-color: {PaletaOscura.ACENTO};
    color: white;
}}
QGroupBox {{
    border: 1px solid {PaletaOscura.BORDE};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    color: {PaletaOscura.ACENTO};
    font-weight: bold;
}}
QStatusBar {{
    background-color: {PaletaOscura.FONDO_PANEL};
    color: {PaletaOscura.TEXTO_TENUE};
}}
QScrollBar:vertical {{
    background: {PaletaOscura.FONDO_PANEL};
    width: 12px;
}}
QScrollBar::handle:vertical {{
    background: {PaletaOscura.BORDE};
    border-radius: 6px;
}}
"""


def aplicar_tema(app) -> None:
    """Aplica el tema oscuro a la aplicación Qt."""
    app.setStyleSheet(HOJA_ESTILOS)
