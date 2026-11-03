import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  UploadCloud,
  FileImage,
  Scan,
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
  RotateCcw,
  Zap,
  Info,
  Clock,
  Layers,
  MapPinOff,
  Sparkles,
  Sliders,
  PlusCircle,
  Check
} from 'lucide-react';
import { api } from '../services/api';
import type {
  ImageAnalysisResponse,
  DetectionItem,
  DetectionStatus,
  Incidente,
  IncidenteCreatePayload
} from '../types';

interface ImageAnalysisSectionProps {
  detectionStatus?: DetectionStatus | null;
  isApiOnline?: boolean;
  onAnalysisComplete?: (result: ImageAnalysisResponse) => void;
  onIncidentCreated?: (inc: Incidente) => void;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png'];

export const ImageAnalysisSection: React.FC<ImageAnalysisSectionProps> = ({
  detectionStatus,
  isApiOnline = true,
  onAnalysisComplete,
  onIncidentCreated
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageMeta, setImageMeta] = useState<{ width: number; height: number; size: number } | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<ImageAnalysisResponse | null>(null);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.5);
  const [saveToStorage, setSaveToStorage] = useState<boolean>(true);
  const [isDragging, setIsDragging] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [registeringDetIds, setRegisteringDetIds] = useState<Record<string, boolean>>({});
  const [registeredIncidentMap, setRegisteredIncidentMap] = useState<Record<string, number>>({});

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Clean up object URLs to avoid memory leaks
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const validateAndSelectFile = (file: File) => {
    setClientError(null);
    setAnalysisResult(null);
    setRegisteredIncidentMap({});
    setShowOriginal(false);

    // 1. Validate extension
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setClientError(`Formato no permitido (${ext}). Se admiten únicamente imágenes JPG, JPEG y PNG.`);
      return;
    }

    // 2. Validate size
    if (file.size === 0) {
      setClientError('El archivo seleccionado está vacío (0 bytes).');
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setClientError(
        `El archivo excede el tamaño máximo permitido de 10 MB (${(file.size / (1024 * 1024)).toFixed(2)} MB).`
      );
      return;
    }

    setSelectedFile(file);

    // Create preview and extract dimensions
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);

    const img = new Image();
    img.onload = () => {
      setImageMeta({
        width: img.naturalWidth,
        height: img.naturalHeight,
        size: file.size
      });
    };
    img.onerror = () => {
      setClientError('No se pudo decodificar el archivo como una imagen válida.');
      setSelectedFile(null);
      setPreviewUrl(null);
      setImageMeta(null);
    };
    img.src = objectUrl;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSelectFile(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSelectFile(e.dataTransfer.files[0]);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile || isAnalyzing) return;

    setIsAnalyzing(true);
    setClientError(null);
    setRegisteredIncidentMap({});

    try {
      const result = await api.analyzeImage(selectedFile, confidenceThreshold, saveToStorage);
      setAnalysisResult(result);
      if (onAnalysisComplete) {
        onAnalysisComplete(result);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error inesperado durante el análisis de la fotografía.';
      setClientError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRegisterAsIncident = async (det: DetectionItem, keyId: string) => {
    if (!analysisResult || registeringDetIds[keyId] || registeredIncidentMap[keyId]) return;

    setRegisteringDetIds((prev) => ({ ...prev, [keyId]: true }));
    setClientError(null);

    const rawCategory = det.normalized_category || det.label || 'otro';
    const validTipo: IncidenteCreatePayload['tipo'] =
      rawCategory === 'poste_luz' ||
      rawCategory === 'vegetacion_invasiva' ||
      rawCategory === 'obstruccion_via'
        ? rawCategory
        : 'otro';

    const validSeveridad: IncidenteCreatePayload['severidad'] =
      det.severity === 'baja' ||
      det.severity === 'media' ||
      det.severity === 'alta' ||
      det.severity === 'critica'
        ? det.severity
        : 'media';

    const payload: IncidenteCreatePayload = {
      drone_id: 'external_upload',
      tipo: validTipo,
      severidad: validSeveridad,
      descripcion:
        det.description ||
        det.justification ||
        `Detección en imagen externa (${analysisResult.original_filename}): ${validTipo}`,
      pos_x: null,
      pos_y: null,
      pos_z: null,
      coordenadas_tipo: 'imagen_externa_sin_gps',
      confidence: det.confidence,
      imagen_id: analysisResult.image_id ?? null,
      estado: det.review_status === 'pendiente_revision' ? 'en_revision' : 'reportado'
    };

    try {
      const created = await api.createIncidente(payload, true);
      setRegisteredIncidentMap((prev) => ({ ...prev, [keyId]: created.id }));
      if (onIncidentCreated) {
        onIncidentCreated(created);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'No se pudo registrar el incidente en SQLite.';
      setClientError(msg);
    } finally {
      setRegisteringDetIds((prev) => ({ ...prev, [keyId]: false }));
    }
  };

  const handleReset = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(null);
    setPreviewUrl(null);
    setImageMeta(null);
    setAnalysisResult(null);
    setClientError(null);
    setRegisteredIncidentMap({});
    setShowOriginal(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getEffectiveCategory = (det: DetectionItem) => {
    return det.normalized_category || det.label || 'otro';
  };

  const getBadgeClass = (category: string) => {
    switch (category) {
      case 'poste_luz':
        return 'badge-class-pole';
      case 'vegetacion_invasiva':
        return 'badge-class-veg';
      case 'obstruccion_via':
        return 'badge-class-obs';
      default:
        return 'badge-secondary';
    }
  };

  const getLabelTitle = (category: string) => {
    switch (category) {
      case 'poste_luz':
        return 'Poste de Luz';
      case 'vegetacion_invasiva':
        return 'Vegetación Invasiva';
      case 'obstruccion_via':
        return 'Obstrucción en Vía';
      case 'otro':
        return 'Anomalía / No Catalogado';
      default:
        return category;
    }
  };

  const getReviewStatusBadge = (status?: string) => {
    switch (status) {
      case 'confirmado':
        return { label: 'Confirmado', className: 'status-tag-confirmed' };
      case 'pendiente_revision':
        return { label: 'Pendiente de Revisión', className: 'status-tag-review' };
      case 'descartado':
        return { label: 'Descartado', className: 'status-tag-dismissed' };
      default:
        return { label: 'Reportado', className: 'status-tag-reported' };
    }
  };

  const resultCategorySummary = useMemo(() => {
    if (!analysisResult) return null;
    const summary = { poste_luz: 0, vegetacion_invasiva: 0, obstruccion_via: 0, otro: 0 };
    for (const d of analysisResult.detections) {
      const cat = d.normalized_category || d.label || 'otro';
      if (cat === 'poste_luz') summary.poste_luz += 1;
      else if (cat === 'vegetacion_invasiva') summary.vegetacion_invasiva += 1;
      else if (cat === 'obstruccion_via') summary.obstruccion_via += 1;
      else summary.otro += 1;
    }
    return summary;
  }, [analysisResult]);

  return (
    <section className="image-analysis-section card">
      {/* Header */}
      <div className="card-header image-analysis-header">
        <div className="card-title-group">
          <div className="logo-shield">
            <Scan className="card-icon text-cyan" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="card-title">ANÁLISIS DE IMÁGENES EXTERNAS (JPG / PNG)</h2>
              <span className="analysis-tag-badge">Inspección Directa</span>
            </div>
            <p className="card-subtitle-text">
              Procesamiento con el motor de visión artificial (Semana 5) y clasificación vial (Semana 6), con registro opcional en SQLite (Semana 8).
            </p>
          </div>
        </div>

        {/* Vision Engine Badge */}
        {detectionStatus && (
          <div className="detector-status-sub">
            <span
              className={`status-badge-mini ${
                detectionStatus.yolo_ready ? 'badge-yolo-active' : 'badge-fallback-active'
              }`}
            >
              {detectionStatus.yolo_ready
                ? `● YOLO Real Activo (${detectionStatus.active_model}) · ${detectionStatus.device.toUpperCase()}`
                : detectionStatus.is_fallback
                ? '▲ Fallback Activo: OpenCV Heurístico'
                : '■ Modo Diagnóstico'}
            </span>
          </div>
        )}
      </div>

      <div className="image-analysis-body">
        {/* Upload Zone / Dropzone (Shown when no file is selected) */}
        {!selectedFile ? (
          <div>
            {clientError && (
              <div className="alert-banner alert-banner-error">
                <AlertTriangle size={18} className="text-red flex-shrink-0" />
                <div className="alert-content">
                  <strong>Archivo rechazado:</strong> {clientError}
                </div>
              </div>
            )}

            <div
              className={`upload-dropzone ${isDragging ? 'dropzone-active' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              <div className="dropzone-icon-wrap">
                <UploadCloud size={44} className="text-cyan animate-pulse" />
              </div>
              <h3 className="dropzone-title">Seleccionar o arrastrar fotografía de inspección</h3>
              <p className="dropzone-sub">
                Formatos admitidos: <strong>JPG, JPEG, PNG</strong> · Tamaño máximo: <strong>10 MB</strong>
              </p>
              <div className="dropzone-hint">
                <span>
                  La imagen se enviará a <code>POST /api/v1/imagenes/analyze</code> y mostrará las detecciones reales devueltas por el backend.
                </span>
              </div>
              <button type="button" className="btn btn-secondary dropzone-btn">
                <FileImage size={16} />
                Examinar archivos en este equipo
              </button>
            </div>
          </div>
        ) : (
          /* File Selected & Preview Mode */
          <div className="analysis-workspace">
            {/* Top Workspace Bar: Metadata & Action Buttons */}
            <div className="workspace-controls-bar">
              <div className="workspace-file-info">
                <FileImage size={20} className="text-cyan" />
                <div className="file-info-details">
                  <span className="file-info-name" title={selectedFile.name}>
                    {selectedFile.name}
                  </span>
                  <span className="file-info-specs">
                    {analysisResult
                      ? `${analysisResult.dimensions.width} × ${analysisResult.dimensions.height} px (${analysisResult.format}) · `
                      : imageMeta
                      ? `${imageMeta.width} × ${imageMeta.height} px · `
                      : ''}
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </span>
                </div>
              </div>

              {/* Advanced Options & Parameters */}
              <div className="workspace-options">
                <div className="option-control">
                  <Sliders size={14} className="text-muted" />
                  <label htmlFor="threshold-slider" className="option-label">
                    Umbral: <strong>{(confidenceThreshold * 100).toFixed(0)}%</strong>
                  </label>
                  <input
                    id="threshold-slider"
                    type="range"
                    min="0.1"
                    max="0.9"
                    step="0.05"
                    value={confidenceThreshold}
                    disabled={isAnalyzing}
                    onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                    className="slider-range"
                  />
                </div>

                <div className="option-control checkbox-control">
                  <input
                    id="save-storage-check"
                    type="checkbox"
                    checked={saveToStorage}
                    disabled={isAnalyzing}
                    onChange={(e) => setSaveToStorage(e.target.checked)}
                  />
                  <label htmlFor="save-storage-check" className="option-label">
                    Guardar captura en SQLite
                  </label>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="workspace-actions">
                <button
                  type="button"
                  className="btn btn-primary analyze-btn"
                  onClick={handleAnalyze}
                  disabled={isAnalyzing || !isApiOnline}
                  title={!isApiOnline ? 'El servidor backend está desconectado' : 'Ejecutar análisis en el backend'}
                >
                  {isAnalyzing ? (
                    <>
                      <div className="btn-spinner" />
                      Analizando Fotografía...
                    </>
                  ) : (
                    <>
                      <Scan size={16} />
                      Iniciar Análisis Visual
                    </>
                  )}
                </button>

                <button
                  type="button"
                  className="btn btn-outline reset-btn"
                  onClick={handleReset}
                  disabled={isAnalyzing}
                  title="Cargar otra imagen"
                >
                  <RotateCcw size={16} />
                  Seleccionar Otra
                </button>
              </div>
            </div>

            {/* Error Message if any */}
            {clientError && (
              <div className="alert-banner alert-banner-error">
                <AlertTriangle size={18} className="text-red flex-shrink-0" />
                <div className="alert-content">
                  <strong>Error en la solicitud:</strong> {clientError}
                </div>
              </div>
            )}

            {/* Main Stage: Image Visualizer + Results */}
            <div className="analysis-stage-grid">
              {/* Left Stage: Image Viewport */}
              <div className="stage-viewport-card">
                <div className="viewport-header">
                  <span className="viewport-title">
                    <Layers size={14} className="text-cyan mr-1 inline" />
                    {analysisResult
                      ? showOriginal
                        ? 'Fotografía Original (Sin Anotaciones)'
                        : 'Fotografía Anotada por el Motor de Visión'
                      : 'Vista Previa de la Fotografía'}
                  </span>

                  {analysisResult?.annotated_image_base64 && (
                    <button
                      type="button"
                      className="btn-toggle-view"
                      onClick={() => setShowOriginal(!showOriginal)}
                    >
                      {showOriginal ? 'Ver con Detecciones' : 'Ver Original'}
                    </button>
                  )}
                </div>

                <div className="image-viewport-container">
                  {isAnalyzing && (
                    <div className="viewport-loading-overlay">
                      <div className="spinner-large" />
                      <p>Ejecutando inferencia en el motor de visión y clasificando anomalías viales...</p>
                    </div>
                  )}

                  {/* Render annotated base64 if available, otherwise raw preview */}
                  <img
                    src={
                      analysisResult?.annotated_image_base64 && !showOriginal
                        ? `data:image/jpeg;base64,${analysisResult.annotated_image_base64}`
                        : previewUrl || ''
                    }
                    alt="Vista previa fotografía externa"
                    className="viewport-image"
                  />
                </div>

                {/* Honest Location Warning Notice */}
                <div className="viewport-location-notice">
                  <MapPinOff size={14} className="text-muted mr-1 inline flex-shrink-0" />
                  <span>
                    <strong>Ubicación geográfica:</strong>{' '}
                    {analysisResult?.location_notice ||
                      'No disponible. Esta fotografía proviene de un archivo externo y no posee telemetría de dron Webots ni coordenadas GPS.'}
                  </span>
                </div>
              </div>

              {/* Right Stage: Results & Detections List */}
              <div className="stage-results-card">
                <div className="viewport-header">
                  <span className="viewport-title">
                    <Sparkles size={14} className="text-cyan mr-1 inline" />
                    Resultados del Motor de Visión & Clasificación
                  </span>
                  {analysisResult && (
                    <span
                      className={`count-pill ${
                        analysisResult.total_valid > 0 ? 'count-pill-active' : 'count-pill-zero'
                      }`}
                    >
                      {analysisResult.total_valid} válida{analysisResult.total_valid === 1 ? '' : 's'}
                      {analysisResult.total_rejected > 0
                        ? ` (${analysisResult.total_rejected} descartada${
                            analysisResult.total_rejected === 1 ? '' : 's'
                          })`
                        : ''}
                    </span>
                  )}
                </div>

                {/* Not Analyzed Yet State */}
                {!analysisResult && !isAnalyzing && (
                  <div className="empty-analysis-state">
                    <Scan size={36} className="text-cyan opacity-40 animate-pulse" />
                    <h4>Fotografía lista para análisis</h4>
                    <p>
                      Haz clic en &ldquo;Iniciar Análisis Visual&rdquo; para enviar la imagen al backend y obtener las detecciones reales.
                    </p>
                  </div>
                )}

                {/* Loading State */}
                {isAnalyzing && (
                  <div className="empty-analysis-state">
                    <div className="spinner-medium text-cyan" />
                    <h4>Procesando fotografía en el servidor...</h4>
                    <p>Aplicando modelos de visión artificial, umbrales de confianza y validación geométrica.</p>
                  </div>
                )}

                {/* Results Loaded */}
                {analysisResult && (
                  <div className="results-content-wrap">
                    {/* Status Banner: Distinguish Success vs No Detections */}
                    {analysisResult.status === 'success' && (
                      <div className="alert-banner alert-banner-success">
                        <CheckCircle2 size={18} className="text-green flex-shrink-0" />
                        <div className="alert-content">
                          <strong>Análisis completado:</strong> Se detectaron{' '}
                          <strong>{analysisResult.total_valid}</strong> elemento(s) válido(s) de{' '}
                          <strong>{analysisResult.total_detected}</strong> en bruto (modelo:{' '}
                          <code>{analysisResult.model_info.name}</code>).
                        </div>
                      </div>
                    )}

                    {analysisResult.status === 'no_detections' && (
                      <div className="alert-banner alert-banner-info">
                        <ShieldCheck size={18} className="text-cyan flex-shrink-0" />
                        <div className="alert-content">
                          <strong>Sin detecciones:</strong> El motor de visión procesó la fotografía correctamente y no encontró postes caídos, vegetación invasiva ni obstrucciones que superen el umbral ({(confidenceThreshold * 100).toFixed(0)}%).
                        </div>
                      </div>
                    )}

                    {/* Category Breakdown Summary */}
                    {resultCategorySummary && analysisResult.detections.length > 0 && (
                      <div className="detection-category-bar" style={{ marginBottom: '0.75rem' }}>
                        <span className="cat-filter-chip cat-chip-pole">
                          <span className="legend-indicator legend-pole"></span>
                          Postes: <strong>{resultCategorySummary.poste_luz}</strong>
                        </span>
                        <span className="cat-filter-chip cat-chip-veg">
                          <span className="legend-indicator legend-veg"></span>
                          Vegetación: <strong>{resultCategorySummary.vegetacion_invasiva}</strong>
                        </span>
                        <span className="cat-filter-chip cat-chip-obs">
                          <span className="legend-indicator legend-obs"></span>
                          Obstáculos: <strong>{resultCategorySummary.obstruccion_via}</strong>
                        </span>
                        {resultCategorySummary.otro > 0 && (
                          <span className="cat-filter-chip">
                            Otros: <strong>{resultCategorySummary.otro}</strong>
                          </span>
                        )}
                      </div>
                    )}

                    {/* Model Limitations & Technical Warnings */}
                    {analysisResult.model_info.warnings && analysisResult.model_info.warnings.length > 0 && (
                      <div className="alert-banner alert-banner-warning">
                        <Info size={18} className="text-amber flex-shrink-0" />
                        <div className="alert-content">
                          <strong>Información del modelo ({analysisResult.model_info.name}):</strong>
                          <ul className="model-warnings-list">
                            {analysisResult.model_info.warnings.map((w, idx) => (
                              <li key={idx}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}

                    {/* Detections List */}
                    <div className="analysis-detections-list">
                      {analysisResult.detections.length === 0 ? (
                        <div className="empty-state">
                          <CheckCircle2 size={28} className="text-green opacity-70" />
                          <p>No se encontraron detecciones en la fotografía analizada.</p>
                        </div>
                      ) : (
                        analysisResult.detections.map((det, idx) => {
                          const keyId = det.id || `det-${idx}`;
                          const category = getEffectiveCategory(det);
                          const reviewStatus = getReviewStatusBadge(det.review_status);
                          const boxW = Math.max(0, det.bbox.x_max - det.bbox.x_min);
                          const boxH = Math.max(0, det.bbox.y_max - det.bbox.y_min);
                          const isRegistered = registeredIncidentMap[keyId] !== undefined;
                          const isRegistering = Boolean(registeringDetIds[keyId]);
                          const showJustification =
                            det.justification && det.justification !== det.description;

                          return (
                            <div key={keyId} className="detection-card-item">
                              <div className="detection-card-top">
                                <div className="flex items-center gap-1 flex-wrap">
                                  <span className={`class-badge ${getBadgeClass(category)}`}>
                                    {getLabelTitle(category)}
                                  </span>
                                  {det.raw_label && det.raw_label !== category && (
                                    <span
                                      className="raw-model-tag"
                                      title={`Etiqueta en bruto devuelta por el modelo: ${det.raw_label}`}
                                    >
                                      modelo: {det.raw_label}
                                    </span>
                                  )}
                                  {det.is_incident_candidate && (
                                    <span className="incident-candidate-tag">
                                      <AlertTriangle size={10} className="inline mr-1" />
                                      Candidato a Incidente
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center gap-1">
                                  <span className={`review-status-pill ${reviewStatus.className}`}>
                                    {reviewStatus.label}
                                  </span>
                                  <span className="confidence-chip">
                                    <Zap size={12} className="text-amber inline mr-1" />
                                    {(det.confidence * 100).toFixed(1)}%
                                  </span>
                                </div>
                              </div>

                              {det.description && <p className="detection-desc">{det.description}</p>}
                              {showJustification && (
                                <p className="detection-justification">
                                  <Info size={11} className="inline mr-1 text-cyan" />
                                  {det.justification}
                                </p>
                              )}

                              {det.validation_passed === false && det.rejection_reason && (
                                <p className="detection-rejection-text">
                                  Rechazada por filtro: {det.rejection_reason}
                                </p>
                              )}

                              <div className="confidence-bar-container">
                                <div
                                  className="confidence-bar-fill"
                                  style={{ width: `${Math.min(100, Math.max(0, det.confidence * 100))}%` }}
                                />
                              </div>

                              <div className="bbox-info">
                                <span>
                                  BBox: [{det.bbox.x_min.toFixed(0)}, {det.bbox.y_min.toFixed(0)}] → [
                                  {det.bbox.x_max.toFixed(0)}, {det.bbox.y_max.toFixed(0)}] (
                                  {boxW.toFixed(0)}×{boxH.toFixed(0)} px)
                                </span>
                                <span className={`severity-tag severity-${det.severity}`}>
                                  Severidad {det.severity}
                                </span>
                              </div>

                              <div className="detection-meta-footer">
                                <span className="sim-coords-absent">
                                  📍 Sin coordenadas (imagen externa)
                                </span>
                                <button
                                  type="button"
                                  className={`btn-register-incident ${
                                    isRegistered ? 'btn-register-done' : ''
                                  }`}
                                  disabled={isRegistering || isRegistered || !isApiOnline}
                                  onClick={() => handleRegisterAsIncident(det, keyId)}
                                  title="Guardar esta detección como incidente en la base de datos SQLite"
                                >
                                  {isRegistered ? (
                                    <>
                                      <Check size={12} /> Guardado en SQLite (#
                                      {registeredIncidentMap[keyId]})
                                    </>
                                  ) : isRegistering ? (
                                    <>Guardando...</>
                                  ) : (
                                    <>
                                      <PlusCircle size={12} /> Registrar Incidente SQLite
                                    </>
                                  )}
                                </button>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>

                    {/* Technical Telemetry & Benchmark Footer */}
                    <div className="analysis-metrics-footer">
                      <div className="metric-chip">
                        <Clock size={12} className="text-cyan mr-1" />
                        <span>
                          Inferencia: <strong>{analysisResult.inference_time_ms} ms</strong>
                        </span>
                      </div>
                      <div className="metric-chip">
                        <Clock size={12} className="text-cyan mr-1" />
                        <span>
                          Clasificación: <strong>{analysisResult.classification_time_ms} ms</strong>
                        </span>
                      </div>
                      <div className="metric-chip">
                        <Clock size={12} className="text-cyan mr-1" />
                        <span>
                          Total: <strong>{analysisResult.processing_time_ms} ms</strong>
                        </span>
                      </div>
                      <div className="metric-chip">
                        <Layers size={12} className="text-muted mr-1" />
                        <span>
                          Backend: <strong>{analysisResult.model_info.backend}</strong> (
                          {analysisResult.model_info.device.toUpperCase()})
                        </span>
                      </div>
                      {analysisResult.stored_filename && (
                        <div
                          className="metric-chip"
                          title={`Almacenado como: ${analysisResult.stored_filename}`}
                        >
                          <span>
                            Imagen SQLite: <strong>ID #{analysisResult.image_id}</strong>
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
