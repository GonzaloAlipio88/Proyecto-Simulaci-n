import type { FC } from 'react';
import { Target, Zap, CheckCircle2 } from 'lucide-react';
import type { DetectionItem } from '../types';

interface DetectionViewerProps {
  detections: DetectionItem[];
}

export const DetectionViewer: FC<DetectionViewerProps> = ({ detections }) => {

  const getBadgeClass = (label: string) => {
    switch (label) {
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

  const getLabelTitle = (label: string) => {
    switch (label) {
      case 'poste_luz':
        return 'Poste de Luz';
      case 'vegetacion_invasiva':
        return 'Vegetación Invasiva';
      case 'obstruccion_via':
        return 'Obstrucción en Vía';
      default:
        return label;
    }
  };

  return (
    <div className="card detection-viewer-card">
      <div className="card-header">
        <div className="card-title-group">
          <Target className="card-icon text-cyan" />
          <h2 className="card-title">INSPECTOR DE VISIÓN ARTIFICIAL (IA)</h2>
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
          detections.map((det, idx) => (
            <div key={idx} className="detection-card-item">
              <div className="detection-card-top">
                <span className={`class-badge ${getBadgeClass(det.label)}`}>
                  {getLabelTitle(det.label)}
                </span>
                <span className="confidence-chip">
                  <Zap size={12} className="text-amber inline mr-1" />
                  {(det.confidence * 100).toFixed(0)}% Confianza
                </span>
              </div>

              {det.description && (
                <p className="detection-desc">{det.description}</p>
              )}

              <div className="confidence-bar-container">
                <div
                  className="confidence-bar-fill"
                  style={{ width: `${det.confidence * 100}%` }}
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
            </div>
          ))
        )}
      </div>
    </div>
  );
};
