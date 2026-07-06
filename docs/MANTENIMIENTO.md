# Instrucciones de mantenimiento

Guía para el mantenimiento, la actualización y la resolución de problemas de la
aplicación a lo largo del tiempo.

## 1. Copias de seguridad

- **Manual**: botón «Copia de seguridad» de la interfaz. Genera un fichero
  `cuadrantes_AAAAMMDD_HHMMSS.db` en la carpeta `copias_seguridad/`.
- **Automática**: la ejecución en modo `--generar` realiza una copia tras exportar.
- **Recomendación**: programar una copia de `datos/cuadrantes.db` a un almacenamiento
  externo o en la nube. Al usar la API `backup` de SQLite, las copias son
  consistentes aunque la aplicación esté en uso.

### Restaurar una copia

1. Cierre la aplicación.
2. Sustituya `datos/cuadrantes.db` por la copia deseada (renómbrela a
   `cuadrantes.db`).
3. Elimine los ficheros `cuadrantes.db-wal` y `cuadrantes.db-shm` si existen.
4. Abra de nuevo la aplicación.

## 2. Base de datos

- Motor: **SQLite** (fichero único en `datos/cuadrantes.db`).
- El esquema se crea/actualiza de forma **idempotente** al arrancar.
- El **historial de cambios** (tabla `historial_cambios`) registra cada operación
  relevante con marca temporal; útil para auditoría y depuración.
- Para inspeccionar la base de datos puede usarse cualquier visor de SQLite
  (por ejemplo, «DB Browser for SQLite»).

## 3. Actualización de la aplicación

1. Realice una copia de seguridad de `datos/cuadrantes.db`.
2. Actualice el código fuente.
3. Reinstale las dependencias por si han cambiado: `pip install -r requirements.txt`.
4. Arranque la aplicación: el esquema se migrará automáticamente si es necesario.

## 4. Ajuste del rendimiento del solucionador

- El tiempo máximo del solucionador se configura en **Configuración → General →
  «Tiempo máx. solucionador»** (por defecto 30 s).
- Para plantillas grandes o muchas restricciones, aumente este valor para obtener
  soluciones más equilibradas.
- Si el resultado tarda demasiado, redúzcalo: el motor devolverá la mejor solución
  encontrada hasta el momento (factible), no fallará.

## 5. Ajuste de las reglas

- Todas las reglas y **pesos** se editan desde el panel de configuración.
- Los pesos son relativos: aumentar uno hace que ese objetivo prevalezca al
  resolver empates entre soluciones válidas.
- Las restricciones individuales de cada trabajador se editan en el gestor de
  trabajadores.

## 6. Resolución de problemas

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| «No se pudo generar» | Restricciones incompatibles | Revise disponibilidad y restricciones del mes; la auditoría indicará el conflicto. |
| Puestos sin cubrir | Personal insuficiente ese día | El cuadrante se marca «con incidencias justificadas»; incorpore refuerzo o ajuste ausencias. |
| La interfaz no arranca en Linux | Faltan bibliotecas de Qt | Instale `libegl1 libgl1 libxkbcommon0` (ver INSTALACION.md). |
| Reparto poco equilibrado | Pesos mal ajustados o poco histórico | Suba el peso del equilibrio o acumule más meses de histórico. |

## 7. Registro y trazabilidad

- Cada alta, modificación, generación y guardado queda registrado en
  `historial_cambios`.
- Los cuadrantes se **versionan**: regenerar un mes no borra la versión anterior,
  lo que permite comparar alternativas (por ejemplo, «con» y «sin» un trabajador).

## 8. Buenas prácticas operativas

- Ejecute la generación el **día 15** para preparar el mes siguiente con margen.
- Complete siempre el asistente con la información real del mes (vacaciones,
  bajas…): la calidad del cuadrante depende de la calidad de los datos.
- Revise la **auditoría** antes de dar por válido un cuadrante.
- Conserve las **exportaciones** (Excel/PDF) como registro documental del servicio.
