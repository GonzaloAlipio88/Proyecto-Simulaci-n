# Directorio de Pesos de Visión Artificial (YOLO)

Este directorio está destinado a almacenar los pesos entrenados del modelo de visión artificial (formato `.pt` de Ultralytics YOLO).

## Convención de Nombres
- Ruta por defecto: `backend/storage/weights/best.pt`
- Variable de entorno configurable: `YOLO_WEIGHTS_PATH`

## Clases de Inspección Soportadas
El modelo debe estar entrenado para detectar:
1. `poste_luz` (Clase 0)
2. `vegetacion_invasiva` (Clase 1)
3. `obstruccion_via` (Clase 2)

## Comportamiento del Sistema sin Pesos
- Si este directorio no contiene el archivo de pesos o si el archivo está ausente, el backend **NO** descarga modelos pesados por defecto ni colapsa.
- El sistema se acoge a la política de resiliencia configurada:
  1. Si `DETECTION_FALLBACK_TO_HEURISTIC=True` (por defecto): Se activa el detector de visión heurístico basado en OpenCV (filtros HSV, Canny y morfología).
  2. Si `DETECTION_FALLBACK_TO_HEURISTIC=False`: Se activa el modo de diagnóstico explícito que informa que los pesos no están disponibles sin inventar detecciones falsas.

## Políticas de Control de Versiones (Git)
Los archivos de pesos (`*.pt`, `*.onnx`, `*.engine`) son binarios de gran tamaño y **NO deben subirse directamente a Git**. Deben obtenerse mediante artefactos de entrenamiento o descargarse de almacenamiento seguro externo.
