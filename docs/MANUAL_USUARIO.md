# Manual de usuario

Guía práctica para generar, revisar, editar y exportar los cuadrantes mensuales.

## 1. La ventana principal

Al abrir la aplicación (`python main.py`) se muestra la ventana principal en modo
oscuro, dividida en:

- **Barra de herramientas** (arriba): generar, exportar (Excel/PDF/informes),
  trabajadores, configuración y copia de seguridad.
- **Panel lateral** (izquierda): selector de mes/año y **histórico** de todos los
  cuadrantes generados.
- **Zona central**: buscador y tres pestañas — **Calendario**, **Auditoría** y
  **Estadísticas**.
- **Barra de estado** (abajo): indicador del estado de la última operación.

## 2. Generar un cuadrante

1. En el panel lateral, seleccione el **mes** y el **año**.
2. Pulse **«Generar con asistente»** (o el botón de la barra de herramientas).
3. Se abre el **asistente**, que le preguntará por:
   - **Vacaciones**: trabajador, fecha de inicio y de fin.
   - **Bajas médicas**: trabajador y fechas.
   - **Permisos y formación**: tipo (retribuido, sin sueldo, formación, asuntos
     propios), trabajador y fechas.
   - **Restricciones individuales**: días en los que un trabajador no puede
     trabajar o preferencias puntuales (indique los días separados por comas).
   - **Incidencias**: cualquier incidencia extraordinaria del mes.
4. Al finalizar, la aplicación ejecuta el **motor de optimización** y muestra el
   cuadrante en el calendario. La barra de estado indica el tiempo de cálculo y el
   estado resultante.

> El programa **nunca** genera un cuadrante sin pasar por el asistente.

## 3. Leer el calendario

- Cada trabajador ocupa **dos filas**: la superior muestra el **turno**
  (`MT` diurno, `TN` noche) y la inferior el **puesto** (`F1`, `F2`, `MO`, `EX`).
- Las columnas de **fin de semana y festivos** aparecen resaltadas.
- Los turnos de **noche** se muestran en cian; los **cambios manuales** en rojo;
  las **vacaciones** en naranja.
- Las tres últimas columnas son **H.T.** (horas trabajadas), **H.E.** (horas
  extraordinarias) y **H.N** (horas nocturnas).
- La última fila muestra el **cómputo de horas diarias** del servicio.

## 4. Auditoría

La pestaña **Auditoría** muestra la comprobación de todas las reglas con su estado
(**Cumple** en verde, **Advertencia** en naranja, **No cumple** en rojo), el
motivo y la solución propuesta. El cuadrante se marca como:

- **Validado**: se cumplen todas las reglas.
- **Generado con incidencias justificadas**: hay advertencias o imposibilidades
  operativas, debidamente explicadas.

## 5. Estadísticas

La pestaña **Estadísticas** muestra gráficos de barras con las horas, noches y
fines de semana por trabajador, además de un resumen general. Sirve para verificar
de un vistazo el equilibrio del reparto.

## 6. Edición manual

- Haga **doble clic** en cualquier celda del calendario para editar la asignación
  (trabajar en un turno-puesto, dejar libre, vacaciones, baja o permiso).
- Tras cada cambio, la aplicación **recalcula** los cómputos, **revalida** todas
  las reglas y **autoguarda** el cuadrante.
- Los cambios manuales se resaltan para distinguirlos de la propuesta automática.

## 7. Buscador y filtros

Escriba en el cuadro **«Buscar»** para filtrar el calendario por nombre de
trabajador. Útil en plantillas grandes.

## 8. Exportar

Desde la barra de herramientas:

- **Exportar Excel**: genera el `.xlsx` con el formato NATURGY.
- **Exportar PDF**: genera el cuadrante imprimible en A3 apaisado.
- **Informes**: genera un PDF con los ocho informes (horas, noches, fines de
  semana, vacaciones, horas extra, equilibrio, incidencias y validación).

## 9. Gestión de trabajadores

En **«Trabajadores»** puede dar de alta, editar o desactivar personal y configurar
sus **restricciones individuales**: puestos habilitados de día y de noche,
prohibición de noches, preferencias y cómputo mensual personal.

## 10. Configuración de reglas

En **«Configuración»** puede ajustar, sin tocar el código, todas las reglas:
parámetros de descanso, fines de semana, adaptación de vacaciones y **pesos** de
los objetivos de la optimización (por ejemplo, dar más importancia al equilibrio
de noches que a la rotación de puestos).

## 11. Copias de seguridad

Pulse **«Copia de seguridad»** para guardar una copia íntegra de la base de datos.
Además, se realiza una copia automática tras cada generación en modo automatizado.
