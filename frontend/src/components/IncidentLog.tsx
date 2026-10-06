import { useState, useEffect, type FC } from 'react';
import { AlertOctagon, Filter, CheckCircle, Clock } from 'lucide-react';
import type { Incidente } from '../types';
import { api } from '../services/api';

interface IncidentLogProps {
  latestWsIncident: Incidente | null;
}

export const IncidentLog: FC<IncidentLogProps> = ({ latestWsIncident }) => {
  const [incidents, setIncidents] = useState<Incidente[]>([]);
  const [typeFilter, setTypeFilter] = useState<string>('all');

  const fetchIncidents = async () => {
    try {
      const data = await api.getIncidentes(typeFilter !== 'all' ? { tipo: typeFilter } : undefined);
      setIncidents(data);
    } catch (err) {
      console.error('Error cargando incidentes:', err);
    }
  };


  useEffect(() => {
    fetchIncidents();
  }, [typeFilter]);

  // When a new incident arrives via WebSocket, prepend to list
  useEffect(() => {
    if (latestWsIncident) {
      setIncidents((prev) => {
        if (prev.some((i) => i.id === latestWsIncident.id)) return prev;
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
        <div className="filter-group">
          <Filter size={14} className="text-cyan inline mr-1" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="filter-select"
          >
            <option value="all">Todas las anomalías</option>
            <option value="poste_luz">Postes de Luz</option>
            <option value="vegetacion_invasiva">Vegetación Invasiva</option>
            <option value="obstruccion_via">Obstrucciones de Vía</option>
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
                <th>ESTADO</th>
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
                    [{inc.pos_x.toFixed(1)}, {inc.pos_y.toFixed(1)}, {inc.pos_z.toFixed(1)}m]
                  </td>
                  <td className="inc-desc" title={inc.descripcion}>
                    {inc.descripcion}
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
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
