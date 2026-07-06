# Generador Automático de Cuadrantes de Seguridad Privada

Aplicación de escritorio profesional que genera automáticamente los **cuadrantes
mensuales** de una empresa de seguridad privada, minimizando la intervención
manual y buscando siempre el reparto **más justo, equilibrado y eficiente**
posible. Aprende del histórico de cuadrantes anteriores para mejorar el reparto
de forma continua.

> Formato aprendido a partir de los cuadrantes reales de **NATURGY – AV. SAN LUIS
> 77**: turnos `MT`/`TN`, puestos `F1`/`F2`/`MO`/`EX`, cómputo mensual de 162 h,
> columnas H.T./H.E./H.N. y estética idéntica (colores, fines de semana en
> amarillo, noches en cian, celdas combinadas).

## 📱 Usar y gestionar todo desde el móvil

Para tener una **URL fija** siempre disponible y gestionarlo por completo desde el
teléfono (sin ordenador ni línea de comandos), publique la versión web en la nube
con un toque:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/luiperax/cuadrantes)

Después, defina la contraseña `CUADRANTES_PASSWORD` en el panel de Render y abra la
URL en el móvil. Guía detallada en [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md).

---

## 1. Características principales

| Área | Descripción |
|------|-------------|
| **Motor de optimización** | CSP con Google OR-Tools (CP-SAT): programación por restricciones, lineal entera, multiobjetivo, heurísticas y *backtracking*. |
| **Asistente previo** | Recaba vacaciones, bajas, permisos, restricciones e incidencias antes de generar. Nunca genera sin preguntar. |
| **Memoria histórica** | Compensa la carga acumulada (horas, noches, fines de semana) de meses anteriores. |
| **Validación y auditoría** | Comprueba todas las reglas y marca el cuadrante como *Validado* o *Generado con incidencias justificadas*. |
| **Edición manual** | Calendario editable con recálculo y revalidación automáticos, y autoguardado. |
| **Exportación** | Excel (formato NATURGY), PDF y copias de seguridad automáticas. |
| **Informes** | Horas, noches, fines de semana, vacaciones, horas extra, equilibrio, incidencias y validación. |
| **Interfaz** | Moderna, en modo oscuro, con calendario, filtros, buscador, panel lateral, indicadores y gráficos. |
| **Configuración** | Todas las reglas se modifican desde un panel, sin tocar el código. |
| **Ejecución automática** | Programador del día 15 (APScheduler) o Programador de tareas de Windows. |

---

## 2. Puesta en marcha rápida

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Abrir la interfaz gráfica
python main.py
```

La primera vez se carga automáticamente una **plantilla de ejemplo** con las
restricciones individuales del pliego (Luis y Fernando solo `F1-MT` sin noches;
Mohamed solo `MO` de día o noches).

### Otros modos de uso

```bash
python main.py --asistente            # Abre el asistente del mes siguiente.
python main.py --programador          # Activa el aviso automático del día 15.
python main.py --generar 2026 9       # Genera y exporta septiembre 2026 sin interfaz.
python main.py --web                  # Versión web, utilizable desde el móvil.
```

### Uso desde el móvil

La versión web (`python main.py --web` o, en Windows, `ejecutar_movil.bat`) levanta
un servidor que reutiliza el mismo motor y se abre desde el navegador del móvil.
Estando en la misma red Wi-Fi, abra en el teléfono la dirección
`http://IP-DEL-PC:8000` que muestra la ventana. Guía completa en
[`docs/USO_MOVIL.md`](docs/USO_MOVIL.md).

Para acceder **desde cualquier lugar**, hay dos caminos:

- **Con alojamiento en la nube** (URL fija siempre disponible): ver
  [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md).
- **Sin alojamiento** (ejecutándolo en su propio ordenador, con Tailscale o
  Cloudflare Tunnel): ver [`docs/ACCESO_SIN_NUBE.md`](docs/ACCESO_SIN_NUBE.md).

---

## 3. Elección tecnológica (justificación)

| Tecnología | Por qué |
|------------|---------|
| **Python 3.10+** | Lenguaje maduro, legible y con el mejor ecosistema de optimización y ofimática. Facilita el mantenimiento a largo plazo. |
| **Google OR-Tools (CP-SAT)** | Solucionador líder para CSP y optimización combinatoria. Integra en un solo motor restricciones duras, objetivos lineales, multiobjetivo, heurísticas y *backtracking*, tal y como exige el pliego. |
| **SQLite** | Base de datos embebida, transaccional y sin servidor. Todo el histórico vive en un único fichero fácil de respaldar; ideal para una aplicación de escritorio pensada para durar años. |
| **OpenPyXL** | Control total sobre estilos de Excel (colores, bordes, celdas combinadas), imprescindible para reproducir el cuadrante NATURGY de forma casi indistinguible. |
| **ReportLab** | Generación de PDF de calidad profesional para el cuadrante imprimible y los informes. |
| **PySide6 (Qt for Python)** | *Framework* de interfaz maduro y multiplataforma, con soporte nativo de temas oscuros y componentes ricos (calendario, tablas, asistentes). |
| **APScheduler** | Programación de tareas robusta e integrada en el proceso, complementada con el Programador de tareas de Windows para el arranque desatendido. |

---

## 4. Arquitectura (resumen)

```
cuadrantes/
├── config/         Constantes del dominio y configuración de reglas.
├── datos/          Base de datos SQLite, modelos y repositorios.
├── dominio/        Calendario, cómputos (H.T./H.E./H.N.) y memoria histórica.
├── motor/          Optimizador OR-Tools (CP-SAT).
├── validacion/     Auditoría y validación de reglas.
├── exportacion/    Exportadores Excel y PDF.
├── informes/       Generación de informes y estadísticas.
├── interfaz/       Interfaz gráfica PySide6 (modo oscuro).
├── programador/    Ejecución automática del día 15.
└── servicio.py     Fachada que orquesta todo el flujo.
```

Documentación detallada en la carpeta [`docs/`](docs/):

- [`ARQUITECTURA.md`](docs/ARQUITECTURA.md) — diseño técnico y flujo de datos.
- [`MANUAL_USUARIO.md`](docs/MANUAL_USUARIO.md) — guía de uso paso a paso.
- [`INSTALACION.md`](docs/INSTALACION.md) — instalación y despliegue.
- [`MANTENIMIENTO.md`](docs/MANTENIMIENTO.md) — copias, actualización y soporte.

---

## 5. Reglas de negocio implementadas

**Restricciones duras** (no se incumplen salvo imposibilidad operativa justificada):

- Cobertura de todos los puestos (día laborable: F1, F2, MO, EX de día + F1, F2 de
  noche = 72 h; fin de semana o festivo: F1, F2 de día + F1, F2 de noche = 48 h).
- Restricciones individuales (p. ej. Luis y Fernando solo `F1-MT` y nunca noches;
  Mohamed solo `MO` de día o cualquier puesto de noche).
- Sábado y domingo del mismo fin de semana los realiza el mismo trabajador.
- Sin encadenar noche → mañana del día siguiente.
- Máximo de días y noches consecutivos.
- Sin noche justo antes de vacaciones ni al reincorporarse.

**Objetivos blandos** (ponderados y equilibrados):

- Equilibrio de horas, horas extra, noches y fines de semana.
- Compensación según la memoria histórica.
- Rotación de puestos, preferencias, recuperación tras noches y descansos agrupados.

---

## 6. Pruebas

```bash
python -m tests.test_optimizador     # Genera un mes y valida las restricciones.
```

El motor resuelve un mes completo de 11 trabajadores en pocos segundos, con
cobertura total y reparto equilibrado (diferencia de horas ≈ un solo turno).
