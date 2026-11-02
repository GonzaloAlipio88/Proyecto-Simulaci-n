import { useState, useEffect, type FC } from 'react';
import { AlertOctagon, Filter, CheckCircle, Clock, Image as ImageIcon, Trash2 } from 'lucide-react';
import type { Incidente } from '../types';
import { api } from '../services/api';

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000') + '/api/v1';

interface IncidentLogProps {
  latestWsIncident: Incidente | null;
}

export const IncidentLog: FC<IncidentLogProps> = ({ latestWsIncident }) => {
  const [incidents, setIncidents] = useState<Incidente[]>([]);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const fetchIncidents = async () => {
    try {
      const filters: Record<string, string> = {};
      if (typeFilter !== 'all') filters.tipo = typeFilter;
      if (severityFilter !== 'all') filters.severidad = severityFilter;
      if (statusFilter !== 'all') filters.estado = statusFilter;

      const data = await api.getIncidentes(Object.keys(filters).length > 0 ? filters : undefined);
      setIncidents(data);
    } catch (err) {
      console.error('Error cargando incidentes:', err);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, [typeFilter, severityFilter, statusFilter]);

  // When a new incident arrives via WebSocket, prepend to list
  useEffect(() => {
    if (latestWsIncident) {
      setIncidents((prev) => {
        if (prev.some((i) => i.id === latestWsIncident.id)) {
          // Update existing if present (repetition or modified)
          return prev.map((i) => (i.id === latestWsIncident.id ? latestWsIncident : i));
        }
        return [latestWsIncident, ...prev];
      });
    }
  }, [latestWsIncident]);

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      const updated = await api.updateIncidente(id, { estado: newStatus });
      setIncidents((prev) => prev.map((i) => (i.id === id ? updated : i)));
    } catch (err) {
      console.error('Error actualizando estado de incidente:', err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm(`¿Está seguro de eliminar permanentemente el incidente #${id}?`)) {
      return;
    }
    try {
      await api.deleteIncidente(id);
      setIncidents((prev) => prev.filter((i) => i.id !== id));
    } catch (err) {
      console.error('Error eliminando incidente:', err);
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case 'critica':
        return 'severity-pill-critica';
      case 'alta':
        return 'severity-pill-alta';
      case 'media':
        return 'severity-pill-media';
      default:
        return 'severity-pill-baja';
    }
  };

  const getTypeName = (tipo: string) => {
    switch (tipo) {
      case 'poste_luz':
        return 'Poste de Luz';
      case 'vegetacion_invasiva':
        return 'Vegetación Invasiva';
      case 'obstruccion_via':
        return 'Obstrucción Vía';
      case 'otro':
        return 'Anomalía / Otro';
      default:
        return tipo;
    }
  };

  return (
    <div className="card incident-log-card">
      <div className="card-header">
        <div className="card-title-group">
          <AlertOctagon className="card-icon text-red" />
          <h2 className="card-title">REGISTRO DE INCIDENTES Y ANOMALÍAS EN VÍA (SQLITE)</h2>
        </div>
        <div className="filter-group" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <Filter size={14} className="text-cyan inline mr-1" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="filter-select"
              title="Filtrar por tipo"
            >
              <option value="all">Todos los tipos</option>
              <option value="poste_luz">Postes de Luz</option>
              <option value="vegetacion_invasiva">Vegetación Invasiva</option>
              <option value="obstruccion_via">Obstrucciones de Vía</option>
              <option value="otro">Otras anomalías</option>
            </select>
          </div>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="filter-select"
            title="Filtrar por severidad"
          >
            <option value="all">Todas severidades</option>
            <option value="critica">Crítica</option>
            <option value="alta">Alta</option>
            <option value="media">Media</option>
            <option value="baja">Baja</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="filter-select"
            title="Filtrar por estado"
          >
            <option value="all">Todos los estados</option>
            <option value="reportado">Reportado</option>
            <option value="en_revision">En Revisión</option>
            <option value="atendido">Atendido</option>
            <option value="descartado">Descartado</option>
          </select>
        </div>
      </div>

      <div className="incidents-table-wrapper">
        {incidents.length === 0 ? (
          <div className="empty-state">
            <CheckCircle size={32} className="text-green opacity-70" />
            <p>No hay incidentes registrados que coincidan con el filtro.</p>
          </div>
        ) : (
          <table className="incidents-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>HORA</th>
                <th>TIPO</th>
                <th>SEVERIDAD</th>
                <th>UBICACIÓN 3D</th>
                <th>DESCRIPCIÓN</th>
                <th>IMAGEN</th>
                <th>ESTADO</th>
                <th>ACCIONES</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.id} className={`incident-row incident-sev-${inc.severidad}`}>
                  <td className="inc-id">#{inc.id}</td>
                  <td className="inc-time">
                    <Clock size={12} className="inline mr-1 opacity-70" />
                    {new Date(inc.timestamp).toLocaleTimeString()}
                  </td>
                  <td>
                    <span className="inc-type-tag">{getTypeName(inc.tipo)}</span>
                  </td>
                  <td>
                    <span className={`severity-pill ${getSeverityBadge(inc.severidad)}`}>
                      {inc.severidad.toUpperCase()}
                    </span>
                  </td>
                  <td className="inc-coords">
                    {inc.pos_x != null && inc.pos_y != null && inc.pos_z != null ? (
                      <span title="Coordenadas locales cartesianas en simulación Webots">
                        [{inc.pos_x.toFixed(1)}, {inc.pos_y.toFixed(1)}, {inc.pos_z.toFixed(1)}m]
                      </span>
                    ) : (
                      <span className="opacity-50 italic">Sin posición</span>
                    )}
                  </td>
                  <td className="inc-desc" title={inc.descripcion}>
                    {inc.descripcion}
                    {inc.confidence > 0 && (
                      <span style={{ fontSize: '0.75rem', opacity: 0.7, marginLeft: '6px' }}>
                        ({(inc.confidence * 100).toFixed(0)}%)
                      </span>
                    )}
                  </td>
                  <td className="inc-image-cell">
                    {inc.imagen_id ? (
                      <a
                        href={`${API_BASE}/incidentes/${inc.id}/imagen?download=true`}
                        target="_blank"
                        rel="noreferrer"
                        title="Ver fotografía capturada vinculada a este incidente"
                        className="incident-image-link"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', color: '#00e5ff', textDecoration: 'none' }}
                      >
                        <ImageIcon size={14} />
                        <span>#{inc.imagen_id}</span>
                      </a>
                    ) : (
                      <span className="opacity-40 italic" style={{ fontSize: '0.8rem' }}>Sin foto</span>
                    )}
                  </td>
                  <td>
                    <select
                      value={inc.estado}
                      onChange={(e) => handleStatusChange(inc.id, e.target.value)}
                      className={`status-select status-select-${inc.estado}`}
                    >
                      <option value="reportado">Reportado</option>
                      <option value="en_revision">En Revisión</option>
                      <option value="atendido">Atendido</option>
                      <option value="descartado">Descartado</option>
                    </select>
                  </td>
                  <td>
                    <button
                      onClick={() => handleDelete(inc.id)}
                      title="Eliminar incidente de la base de datos"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#ff5252',
                        cursor: 'pointer',
                        padding: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        opacity: 0.8
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                      onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.8')}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
