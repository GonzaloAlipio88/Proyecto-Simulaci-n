import { useState, useMemo, type FC } from 'react';
import { Target, Zap, CheckCircle2, Scan, WifiOff, AlertTriangle, Info } from 'lucide-react';
import type { DetectionItem, DetectionStatus, RoadCategoriesConfig } from '../types';

interface DetectionViewerProps {
  detections: DetectionItem[];
  detectionStatus?: DetectionStatus | null;
  categoriesConfig?: RoadCategoriesConfig | null;
  hasActiveFrame?: boolean;
  sourceLabel?: string;
  isApiOnline?: boolean;
}

export const DetectionViewer: FC<DetectionViewerProps> = ({
  detections,
  detectionStatus = null,
  categoriesConfig = null,
  hasActiveFrame = false,
  sourceLabel = 'Stream Webots',
  isApiOnline = true
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const getEffectiveCategory = (det: DetectionItem) => {
    return det.normalized_category || det.label || 'otro';
  };

  const categoryCounts = useMemo(() => {
    const counts = {
      all: detections.length,
      poste_luz: 0,
      vegetacion_invasiva: 0,
      obstruccion_via: 0,
      otro: 0
    };
    for (const det of detections) {
      const cat = det.normalized_category || det.label || 'otro';
      if (cat === 'poste_luz') counts.poste_luz += 1;
      else if (cat === 'vegetacion_invasiva') counts.vegetacion_invasiva += 1;
      else if (cat === 'obstruccion_via') counts.obstruccion_via += 1;
      else counts.otro += 1;
    }
    return counts;
  }, [detections]);

  const filteredDetections = useMemo(() => {
    if (selectedCategory === 'all') return detections;
    return detections.filter((d) => (d.normalized_category || d.label || 'otro') === selectedCategory);
  }, [detections, selectedCategory]);

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

  const thresholds = categoriesConfig?.default_thresholds;

  return (
    <div className="card detection-viewer-card">
      <div className="card-header">
        <div className="card-title-group">
          <Target className="card-icon text-cyan" />
          <div>
            <h2 className="card-title">INSPECTOR DE VISIÓN ARTIFICIAL (IA)</h2>
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
                {detectionStatus.model_mode && (
                  <span className="detector-mode-tag">
                    {detectionStatus.model_mode === 'pretrained_generic'
                      ? 'Preentrenado COCO (Mapeo Vial)'
                      : 'Especializado Vial'}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="detection-header-right">
          {hasActiveFrame && <span className="source-tag-mini">{sourceLabel}</span>}
          <span className="count-pill">{detections.length} detecciones</span>
        </div>
      </div>

      {/* Category Breakdown & Filter Chips (Postes, Vegetación, Obstáculos) */}
      <div className="detection-category-bar">
        <button
          type="button"
          className={`cat-filter-chip ${selectedCategory === 'all' ? 'cat-chip-active' : ''}`}
          onClick={() => setSelectedCategory('all')}
        >
          <span>Todas</span>
          <strong>{categoryCounts.all}</strong>
        </button>
        <button
          type="button"
          className={`cat-filter-chip cat-chip-pole ${
            selectedCategory === 'poste_luz' ? 'cat-chip-active' : ''
          }`}
          onClick={() => setSelectedCategory('poste_luz')}
          title={
            thresholds?.poste_luz
              ? `Umbral configurado para Postes de Luz: ${(thresholds.poste_luz * 100).toFixed(0)}%`
              : 'Postes de Luz'
          }
        >
          <span className="legend-indicator legend-pole"></span>
          <span>Postes</span>
          <strong>{categoryCounts.poste_luz}</strong>
        </button>
        <button
          type="button"
          className={`cat-filter-chip cat-chip-veg ${
            selectedCategory === 'vegetacion_invasiva' ? 'cat-chip-active' : ''
          }`}
          onClick={() => setSelectedCategory('vegetacion_invasiva')}
          title={
            thresholds?.vegetacion_invasiva
              ? `Umbral configurado para Vegetación Invasiva: ${(
                  thresholds.vegetacion_invasiva * 100
                ).toFixed(0)}%`
              : 'Vegetación Invasiva'
          }
        >
          <span className="legend-indicator legend-veg"></span>
          <span>Vegetación</span>
          <strong>{categoryCounts.vegetacion_invasiva}</strong>
        </button>
        <button
          type="button"
          className={`cat-filter-chip cat-chip-obs ${
            selectedCategory === 'obstruccion_via' ? 'cat-chip-active' : ''
          }`}
          onClick={() => setSelectedCategory('obstruccion_via')}
          title={
            thresholds?.obstruccion_via
              ? `Umbral configurado para Obstrucciones: ${(thresholds.obstruccion_via * 100).toFixed(0)}%`
              : 'Obstrucciones en Vía'
          }
        >
          <span className="legend-indicator legend-obs"></span>
          <span>Obstáculos</span>
          <strong>{categoryCounts.obstruccion_via}</strong>
        </button>
        {categoryCounts.otro > 0 && (
          <button
            type="button"
            className={`cat-filter-chip ${selectedCategory === 'otro' ? 'cat-chip-active' : ''}`}
            onClick={() => setSelectedCategory('otro')}
          >
            <span>Otros</span>
            <strong>{categoryCounts.otro}</strong>
          </button>
        )}
      </div>

      <div className="detections-list">
        {!isApiOnline ? (
          <div className="empty-state">
            <WifiOff size={30} className="text-red opacity-75" />
            <p>Sin conexión con el backend. No es posible consultar el estado del motor de visión.</p>
          </div>
        ) : !hasActiveFrame && detections.length === 0 ? (
          <div className="empty-state">
            <Scan size={30} className="text-cyan opacity-60" />
            <p>
              Sin fotograma activo en inspección. Inicie el flujo desde Webots o cargue una imagen JPG/PNG abajo para visualizar las detecciones reales.
            </p>
          </div>
        ) : filteredDetections.length === 0 ? (
          <div className="empty-state">
            <CheckCircle2 size={32} className="text-green opacity-70" />
            <p>
              {selectedCategory === 'all'
                ? 'Vía despejada. No se detectan anomalías en el encuadre analizado.'
                : `No hay detecciones de la categoría "${getLabelTitle(selectedCategory)}" en el encuadre actual.`}
            </p>
          </div>
        ) : (
          filteredDetections.map((det, idx) => {
            const category = getEffectiveCategory(det);
            const reviewStatus = getReviewStatusBadge(det.review_status);
            const boxWidth = Math.max(0, det.bbox.x_max - det.bbox.x_min);
            const boxHeight = Math.max(0, det.bbox.y_max - det.bbox.y_min);
            const showJustification =
              det.justification && det.justification !== det.description;

            return (
              <div key={det.id || idx} className="detection-card-item">
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
                      <span
                        className="incident-candidate-tag"
                        title="Esta detección cumple los criterios viales para registrarse como incidente"
                      >
                        <AlertTriangle size={10} className="inline mr-1" />
                        {det.incident_id ? `Incidente #${det.incident_id}` : 'Candidato a Incidente'}
                      </span>
                    )}
                    {det.is_duplicate && (
                      <span
                        className="dedup-tag"
                        title="Detección repetida amortiguada por ventana de deduplicación"
                      >
                        x{det.repetition_count || 2}
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

                <div className="confidence-bar-container">
                  <div
                    className="confidence-bar-fill"
                    style={{ width: `${Math.min(100, Math.max(0, det.confidence * 100))}%` }}
                  ></div>
                </div>

                <div className="bbox-info">
                  <span>
                    BBox: [{det.bbox.x_min.toFixed(0)}, {det.bbox.y_min.toFixed(0)}] → [
                    {det.bbox.x_max.toFixed(0)}, {det.bbox.y_max.toFixed(0)}] ({boxWidth.toFixed(0)}×
                    {boxHeight.toFixed(0)} px)
                  </span>
                  <span className={`severity-tag severity-${det.severity}`}>
                    Severidad {det.severity}
                  </span>
                </div>

                {/* Local simulation location vs GPS */}
                <div className="detection-meta-footer">
                  {det.simulation_coords ? (
                    <span
                      className="sim-coords-text"
                      title={`Coordenadas métricas en ${
                        det.coordinate_system || 'simulation_webots_cartesian_meters'
                      }`}
                    >
                      📍 Sim: [{det.simulation_coords.pos_x.toFixed(1)},{' '}
                      {det.simulation_coords.pos_y.toFixed(1)},{' '}
                      {det.simulation_coords.pos_z.toFixed(1)} m]
                    </span>
                  ) : (
                    <span className="sim-coords-absent">
                      📍 Sin posición de simulación (GPS no disponible)
                    </span>
                  )}
                  <div className="detection-meta-right">
                    {det.frame_id && <span className="frame-id-tag">#{det.frame_id}</span>}
                    {det.timestamp && (
                      <span className="detection-time-text">
                        ⏱ {new Date(det.timestamp).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
