import React, { useState, useRef, useEffect } from 'react';
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
  Sliders
} from 'lucide-react';
import { api } from '../services/api';
import type { ImageAnalysisResponse, DetectionItem, DetectionStatus } from '../types';

interface ImageAnalysisSectionProps {
  detectionStatus?: DetectionStatus | null;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png'];

export const ImageAnalysisSection: React.FC<ImageAnalysisSectionProps> = ({ detectionStatus }) => {
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
      setClientError(`El archivo excede el tamaño máximo permitido de 10 MB (${(file.size / (1024 * 1024)).toFixed(2)} MB).`);
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

    try {
      const result = await api.analyzeImage(selectedFile, confidenceThreshold, saveToStorage);
      setAnalysisResult(result);
    } catch (err: any) {
      setClientError(err.message || 'Error inesperado durante el análisis de la fotografía.');
    } finally {
      setIsAnalyzing(false);
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
              <span className="analysis-tag-badge">Semana 7</span>
            </div>
            <p className="card-subtitle-text">
              Procesamiento con el mismo motor de visión artificial (Semana 5) y clasificación vial (Semana 6), sin depender de Webots.
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
              <span>La imagen se analizará mediante la capa existente de detección y clasificación vial.</span>
            </div>
            <button type="button" className="btn btn-secondary dropzone-btn">
              <FileImage size={16} />
              Examinar archivos en este equipo
            </button>
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
                    {imageMeta ? `${imageMeta.width} × ${imageMeta.height} px · ` : ''}
                    {(selectedFile.size / 1024).toFixed(1)} KB ·{' '}
                    {selectedFile.type || selectedFile.name.split('.').pop()?.toUpperCase()}
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
                    Almacenar análisis (SQLite)
                  </label>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="workspace-actions">
                <button
                  type="button"
                  className="btn btn-primary analyze-btn"
                  onClick={handleAnalyze}
                  disabled={isAnalyzing}
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
                        : 'Fotografía Anotada (Cajas Delimitadoras & Clases)'
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
                    <strong>Ubicación geográfica:</strong> No disponible. Esta fotografía proviene de un archivo externo y no posee telemetría de dron Webots ni coordenadas GPS simuladas.
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
                      {analysisResult.total_valid} anomalía{analysisResult.total_valid === 1 ? '' : 's'}
                    </span>
                  )}
                </div>

                {/* Not Analyzed Yet State */}
                {!analysisResult && !isAnalyzing && (
                  <div className="empty-analysis-state">
                    <Scan size={36} className="text-cyan opacity-40 animate-pulse" />
                    <h4>Fotografía lista para análisis</h4>
                    <p>Haz clic en "Iniciar Análisis Visual" para ejecutar la detección y clasificación de anomalías viales.</p>
                  </div>
                )}

                {/* Loading State */}
                {isAnalyzing && (
                  <div className="empty-analysis-state">
                    <div className="spinner-medium text-cyan" />
                    <h4>Procesando fotografía...</h4>
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
                          <strong>Análisis completado:</strong> Se identificaron{' '}
                          <strong>{analysisResult.total_valid}</strong> elemento(s) catalogado(s) que superaron el umbral de confianza.
                        </div>
                      </div>
                    )}

                    {analysisResult.status === 'no_detections' && (
                      <div className="alert-banner alert-banner-info">
                        <ShieldCheck size={18} className="text-cyan flex-shrink-0" />
                        <div className="alert-content">
                          <strong>Vía despejada:</strong> No se detectaron postes caídos, vegetación invasiva ni obstrucciones en la fotografía.
                        </div>
                      </div>
                    )}

                    {/* Model Limitations & Technical Warnings */}
                    {analysisResult.model_info.warnings && analysisResult.model_info.warnings.length > 0 && (
                      <div className="alert-banner alert-banner-warning">
                        <Info size={18} className="text-amber flex-shrink-0" />
                        <div className="alert-content">
                          <strong>Transparencia técnica:</strong>
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
                          <p>No se encontraron detecciones para presentar.</p>
                        </div>
                      ) : (
                        analysisResult.detections.map((det, idx) => {
                          const category = getEffectiveCategory(det);
                          const reviewStatus = getReviewStatusBadge(det.review_status);
                          return (
                            <div key={det.id || idx} className="detection-card-item">
                              <div className="detection-card-top">
                                <div className="flex items-center gap-1">
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
                                </div>
                                <div className="flex items-center gap-1">
                                  <span className={`review-status-pill ${reviewStatus.className}`}>
                                    {reviewStatus.label}
                                  </span>
                                  <span className="confidence-chip">
                                    <Zap size={12} className="text-amber inline mr-1" />
                                    {(det.confidence * 100).toFixed(0)}% Confianza
                                  </span>
                                </div>
                              </div>

                              {det.description && <p className="detection-desc">{det.description}</p>}

                              <div className="confidence-bar-container">
                                <div
                                  className="confidence-bar-fill"
                                  style={{ width: `${Math.min(100, Math.max(0, det.confidence * 100))}%` }}
                                />
                              </div>

                              <div className="bbox-info">
                                <span>
                                  BBox: [{det.bbox.x_min.toFixed(0)}, {det.bbox.y_min.toFixed(0)}] a [
                                  {det.bbox.x_max.toFixed(0)}, {det.bbox.y_max.toFixed(0)}]
                                </span>
                                <span className={`severity-tag severity-${det.severity}`}>
                                  Severidad {det.severity}
                                </span>
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
                        <span>Inferencia: <strong>{analysisResult.inference_time_ms} ms</strong></span>
                      </div>
                      <div className="metric-chip">
                        <Clock size={12} className="text-cyan mr-1" />
                        <span>Clasificación: <strong>{analysisResult.classification_time_ms} ms</strong></span>
                      </div>
                      <div className="metric-chip">
                        <Clock size={12} className="text-cyan mr-1" />
                        <span>Total: <strong>{analysisResult.processing_time_ms} ms</strong></span>
                      </div>
                      <div className="metric-chip">
                        <Layers size={12} className="text-muted mr-1" />
                        <span>Backend: <strong>{analysisResult.model_info.backend}</strong></span>
                      </div>
                      {analysisResult.stored_filename && (
                        <div className="metric-chip" title={`Almacenado como: ${analysisResult.stored_filename}`}>
                          <span>Guardado: <strong>ID #{analysisResult.image_id}</strong></span>
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
