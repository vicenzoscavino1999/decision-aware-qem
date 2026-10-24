# Guía de reproducción — manuscrito v45

Esta guía utiliza el paquete de código **1.2.0** y el manuscrito **v45**. Ejecuta los pasos en orden, desde la carpeta que contiene `README.md`, `Dockerfile` y `reproduce.py`.

## 1. Preparar el entorno

Extrae el paquete o descarga el repositorio. Necesitas Docker iniciado en modo de contenedores Linux. Construye la imagen:

```sh
docker build --platform linux/amd64 -t daqem:1.2.0 .
```

La imagen fija Python 3.12.10 y las versiones y hashes de las bibliotecas científicas. La construcción requiere internet; la ejecución utiliza los datos incluidos, sin conexión.

## 2. Elegir dónde guardar los resultados

Crea una carpeta fuera del paquete. Elige el bloque correspondiente a tu terminal.

**PowerShell, en Windows:**

```powershell
New-Item -ItemType Directory -Force ../daqem-results | Out-Null
$repro = (Resolve-Path -LiteralPath '../daqem-results').Path
```

**Bash, en Linux o macOS:**

```bash
mkdir -p ../daqem-results
repro="$(cd ../daqem-results && pwd)"
```

Conserva la sesión abierta. Si abres otra terminal, vuelve a definir `repro` con la misma ruta.

## 3. Ejecutar la reproducción

Este comando sirve en ambas terminales:

```sh
docker run --rm --network none --platform linux/amd64 --mount "type=bind,source=$repro,target=/reports" daqem:1.2.0 --mode all --workers 8 --output /reports/run
```

El programa ejecuta las pruebas numéricas, tres repeticiones del núcleo determinista, los siete análisis principales y la generación de cinco figuras. Después comprueba PEC firmado y las particiones de E1, y contrasta las cifras con la v45. También reproduce el ejemplo de identificabilidad con aritmética racional exacta.

`--workers 8` solicita ocho procesos en las etapas que admiten paralelismo. Puedes usar `4` o `2` para reducir el consumo de recursos. Los mensajes `ANALYSIS` y `SUPPLEMENT` identifican la etapa en curso.

## 4. Comprobar que terminó

La terminal debe mostrar `REPRODUCE_PASS: all`. Dentro de `daqem-results/` encontrarás:

| Archivo | Resultado esperado |
|---|---|
| `run/execution.json` | `status: complete`, con las etapas `fast`, `analysis` y `supplements`. |
| `run/tests.xml` | Todas las pruebas aprobadas. |
| `run/reference_comparison.json` | Comparación de los análisis recalculados con sus referencias. |
| `run/supplements.json` | `status: complete`; 49.152 decisiones PEC y 403.200 decisiones E1 comprobadas. |

`supplements.json` indica dónde están los informes de las 71 comprobaciones del manuscrito y del ejemplo de readout. Las entradas y los informes nuevos se conservan por separado.

## 5. Consultar los resultados y el artículo

Los análisis están en `run/analysis/results/` y las figuras regeneradas en `run/figures/`. El [mapa de resultados](RESULTS.md) relaciona los archivos con las tablas, figuras y secciones del artículo.

El PDF incluido es [decision_residual_fields_theory_v45.pdf](../decision_residual_fields_theory_v45.pdf). La figura 1 se entrega con su fuente editable de TikZ; la figura 2 se dibuja dentro de la fuente del artículo.

## Reanudar o repetir

Para reanudar, repite el paso 3 con la misma carpeta y el mismo paquete. Los bloques de análisis completos se comprueban antes de reutilizarlos; los suplementos se vuelven a comprobar en una subcarpeta nueva.

Para otra ejecución independiente, cambia `daqem-results` por un nombre nuevo en el paso 2. Si una etapa falla, consulta el error final y su `.log`; `execution.json` queda marcado como incompleto.

Las [opciones de ejecución](OPTIONAL.md) explican cómo volver a ajustar E1, reconstruir E2 desde los shots, generar otra instancia y compilar el PDF. El [documento de métodos](METHODS.md) detalla qué se recalcula a partir de cada entrada archivada.
