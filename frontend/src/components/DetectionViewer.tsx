import type { FC } from 'react';
import { Target, Zap, CheckCircle2 } from 'lucide-react';
import type { DetectionItem, DetectionStatus } from '../types';

interface DetectionViewerProps {
  detections: DetectionItem[];
  detectionStatus?: DetectionStatus | null;
}

export const DetectionViewer: FC<DetectionViewerProps> = ({ detections, detectionStatus = null }) => {

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
    <div className="card detection-viewer-card">
      <div className="card-header">
        <div className="card-title-group">
          <Target className="card-icon text-cyan" />
          <div>
            <h2 className="card-title">INSPECTOR DE VISIÓN ARTIFICIAL (IA)</h2>
            {detectionStatus && (
              <div className="detector-status-sub">
                <span className={`status-badge-mini ${detectionStatus.yolo_ready ? 'badge-yolo-active' : 'badge-fallback-active'}`}>
                  {detectionStatus.yolo_ready
                    ? `● YOLO Real Activo (${detectionStatus.active_model}) · ${detectionStatus.device.toUpperCase()}`
                    : detectionStatus.is_fallback
                    ? '▲ Fallback Activo: OpenCV Heurístico'
                    : '■ Diagnóstico'}
                </span>
                {detectionStatus.model_mode && (
                  <span className="detector-mode-tag">
                    {detectionStatus.model_mode === 'pretrained_generic' ? 'Modo Preentrenado COCO' : 'Especializado Vial'}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        <span className="count-pill">{detections.length} activos</span>
      </div>

      <div className="detections-list">
        {detections.length === 0 ? (
          <div className="empty-state">
            <CheckCircle2 size={32} className="text-green opacity-70" />
            <p>Vía despejada. No se detectan anomalías en el encuadre actual.</p>
          </div>
        ) : (
          detections.map((det, idx) => {
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
                      <span className="raw-model-tag" title={`Etiqueta en bruto devuelta por el modelo: ${det.raw_label}`}>
                        modelo: {det.raw_label}
                      </span>
                    )}
                    {det.is_duplicate && (
                      <span className="dedup-tag" title="Detección repetida amortiguada por ventana de deduplicación">
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
                      {(det.confidence * 100).toFixed(0)}% Confianza
                    </span>
                  </div>
                </div>

                {det.description && (
                  <p className="detection-desc">{det.description}</p>
                )}

                <div className="confidence-bar-container">
                  <div
                    className="confidence-bar-fill"
                    style={{ width: `${Math.min(100, Math.max(0, det.confidence * 100))}%` }}
                  ></div>
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

                {/* Local simulation location vs GPS */}
                <div className="detection-meta-footer">
                  {det.simulation_coords ? (
                    <span className="sim-coords-text" title="Coordenadas métricas cartesianas en simulación Webots">
                      📍 Sim: [{det.simulation_coords.pos_x.toFixed(1)}, {det.simulation_coords.pos_y.toFixed(1)}, {det.simulation_coords.pos_z.toFixed(1)}m]
                    </span>
                  ) : (
                    <span className="sim-coords-absent">
                      📍 Sin posición simulación
                    </span>
                  )}
                  {det.timestamp && (
                    <span className="detection-time-text">
                      ⏱ {new Date(det.timestamp).toLocaleTimeString()} UTC
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
