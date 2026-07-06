# Arquitectura técnica

Este documento describe el diseño interno de la aplicación, sus capas y el flujo
de datos completo, desde la petición del usuario hasta la entrega del cuadrante
validado.

## 1. Visión general por capas

La aplicación sigue una arquitectura por capas con dependencias unidireccionales
(de arriba hacia abajo), lo que facilita el mantenimiento y las pruebas:

```
┌───────────────────────────────────────────────┐
│  Interfaz gráfica (PySide6) / CLI (main.py)    │  Presentación
├───────────────────────────────────────────────┤
│  ServicioCuadrantes (servicio.py)              │  Orquestación
├───────────────────────────────────────────────┤
│  Motor · Validación · Exportación · Informes   │  Lógica de negocio
├───────────────────────────────────────────────┤
│  Dominio (calendario, cómputos, histórico)     │  Modelo del dominio
├───────────────────────────────────────────────┤
│  Datos (SQLite, modelos, repositorios)         │  Persistencia
└───────────────────────────────────────────────┘
```

## 2. Módulos

### 2.1. `config/`
- **`constantes.py`**: conocimiento del dominio aprendido del cuadrante NATURGY
  (turnos `MT`/`TN`, puestos `F1`/`F2`/`MO`/`EX`, horarios, cobertura por tipo de
  día, colores, letras de día, cómputo mensual). Fuente única de la verdad.
- **`configuracion.py`**: reglas parametrizables (descansos, fines de semana,
  vacaciones, pesos de la optimización). Serializable a JSON.

### 2.2. `datos/`
- **`base_datos.py`**: conexión SQLite, esquema idempotente, transacciones,
  historial de cambios y copias de seguridad (API `backup` de SQLite).
- **`modelos.py`**: entidades del dominio (`Trabajador`, `Cuadrante`,
  `Asignacion`, `Ausencia`, `RestriccionTemporal`, `Festivo`, `Incidencia`…).
- **`repositorios.py`**: conversión modelo ↔ SQL (patrón *Repository*).
- **`datos_iniciales.py`**: plantilla de ejemplo con las restricciones del pliego.

### 2.3. `dominio/`
- **`calendario.py`**: días del mes, fines de semana, festivos y emparejamiento
  sábado-domingo.
- **`computos.py`**: cálculo de H.T. (horas trabajadas), H.E. (extra) y H.N.
  (nocturnas), además de noches, fines de semana y festivos por trabajador.
- **`historico.py`**: agrega la carga de meses anteriores y calcula las
  «deudas» relativas para el equilibrio.

### 2.4. `motor/`
- **`optimizador.py`**: construye y resuelve el modelo CP-SAT (ver sección 4).

### 2.5. `validacion/`
- **`auditoria.py`**: batería de reglas que devuelve, por cada una, estado
  (Cumple/Advertencia/No cumple), motivo, trabajadores afectados y solución
  propuesta. Determina el estado final del cuadrante.

### 2.6. `exportacion/` e `informes/`
- **`excel.py`** / **`pdf.py`**: reproducen el cuadrante en Excel y PDF.
- **`generador.py`**: los ocho informes exigidos + volcado conjunto a PDF.

### 2.7. `interfaz/`
- Ventana principal, asistente, calendario editable, panel de configuración,
  gestor de trabajadores, gráficos y tema oscuro.

### 2.8. `programador/`
- **`planificador.py`**: APScheduler (día 15) + generación del comando para el
  Programador de tareas de Windows.

## 3. Flujo de generación

1. El usuario elige mes/año y abre el **asistente**.
2. El asistente recaba vacaciones, bajas, permisos, restricciones e incidencias y
   los persiste en SQLite.
3. `ServicioCuadrantes.generar()` reúne plantilla activa, ausencias,
   restricciones, festivos e **histórico**, y calcula la carga acumulada.
4. `OptimizadorCuadrante` construye el modelo CP-SAT y lo resuelve.
5. `Auditor` valida el resultado y fija el estado (`VALIDADO` o
   `GENERADO_CON_INCIDENCIAS`).
6. El cuadrante se guarda con versionado y se muestra en el calendario.
7. El usuario puede editar manualmente (con revalidación y autoguardado) y
   exportar a Excel/PDF e informes.

## 4. Modelo de optimización (CP-SAT)

**Variable de decisión**: `x[t, d, turno, puesto] ∈ {0,1}` — el trabajador `t`
cubre ese turno-puesto el día `d`. Solo se crea si el trabajador está habilitado y
disponible.

**Restricciones duras**:
- Un turno como máximo por trabajador y día.
- Cobertura de cada puesto requerido (con variable de holgura muy penalizada para
  poder detectar y justificar la imposibilidad en lugar de fallar).
- Restricciones individuales (habilitación de puestos y prohibición de noches).
- Sin noche → mañana siguiente.
- Sábado y domingo emparejados por trabajador.
- Ventanas deslizantes para días y noches consecutivos.
- Sin noche antes/después de vacaciones.

**Función objetivo** (minimización ponderada):
- Penalización muy alta por puesto sin cubrir.
- Rango (máx − mín) de horas, noches y fines de semana.
- Compensación histórica (coste proporcional al exceso de meses previos).
- Tope de fines de semana con holgura penalizada.
- Recompensa por respetar preferencias de turno.

Los pesos son configurables, de modo que la política de reparto puede ajustarse
sin tocar el código.

## 5. Persistencia y seguridad

- **Transacciones** en todas las escrituras (confirmación/reversión).
- **Modo WAL** de SQLite para mayor robustez ante cortes.
- **Historial de cambios** con marca temporal por cada operación relevante.
- **Autoguardado** tras cada edición manual.
- **Copias de seguridad** íntegras bajo demanda y tras la generación automática.
- **Versionado** de cuadrantes: cada regeneración de un mes crea una nueva versión.
