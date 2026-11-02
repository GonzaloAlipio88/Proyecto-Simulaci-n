import { useState, useEffect, useCallback, useMemo, type FC } from 'react';
import {
  AlertOctagon,
  Filter,
  CheckCircle,
  Clock,
  RefreshCw,
  AlertTriangle
} from 'lucide-react';
import type { Incidente } from '../types';
import { api } from '../services/api';

interface IncidentLogProps {
  latestWsIncident: Incidente | null;
  latestUpdatedIncident?: Incidente | null;
  latestDeletedIncident?: { id: number; ts: number } | null;
  newlyCreatedIncident?: Incidente | null;
  isApiOnline?: boolean;
}

export const IncidentLog: FC<IncidentLogProps> = ({
  latestWsIncident,
  latestUpdatedIncident = null,
  latestDeletedIncident = null,
  newlyCreatedIncident = null,
  isApiOnline = true
}) => {
  const [incidents, setIncidents] = useState<Incidente[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const fetchIncidents = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const filters: {
        tipo?: string;
        severidad?: string;
        estado?: string;
        limit?: number;
      } = { limit: 100 };

      if (typeFilter !== 'all') filters.tipo = typeFilter;
      if (severityFilter !== 'all') filters.severidad = severityFilter;
      if (statusFilter !== 'all') filters.estado = statusFilter;

      const data = await api.getIncidentes(filters);
      setIncidents(data);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Error al consultar el historial de incidentes en SQLite.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [typeFilter, severityFilter, statusFilter]);

  // Reload when filters change or when backend comes back online
  useEffect(() => {
    let active = true;
    const triggerLoad = async () => {
      if (!active) return;
      await fetchIncidents();
    };
    triggerLoad();
    return () => {
      active = false;
    };
  }, [fetchIncidents, isApiOnline]);

  // Merge incoming live / newly created / updated incidents
  const mergedIncidents = useMemo(() => {
    let list = [...incidents];

    const upsertItem = (item: Incidente | null) => {
      if (!item) return;
      if (typeFilter !== 'all' && item.tipo !== typeFilter) return;
      if (severityFilter !== 'all' && item.severidad !== severityFilter) return;
      if (statusFilter !== 'all' && item.estado !== statusFilter) return;

      const idx = list.findIndex((i) => i.id === item.id);
      if (idx >= 0) {
        list[idx] = item;
      } else {
        list = [item, ...list];
      }
    };

    upsertItem(newlyCreatedIncident);
    upsertItem(latestWsIncident);
    upsertItem(latestUpdatedIncident);

    if (latestDeletedIncident) {
      list = list.filter((i) => i.id !== latestDeletedIncident.id);
    }

    return list;
  }, [
    incidents,
    newlyCreatedIncident,
    latestWsIncident,
    latestUpdatedIncident,
    latestDeletedIncident,
    typeFilter,
    severityFilter,
    statusFilter
  ]);

  const handleStatusChange = async (id: number, newStatus: string) => {
    setUpdatingId(id);
    setActionError(null);
    try {
      const updated = await api.updateIncidente(id, { estado: newStatus });
      setIncidents((prev) => prev.map((i) => (i.id === id ? updated : i)));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `No se pudo actualizar el incidente #${id}`;
      setActionError(msg);
    } finally {
      setUpdatingId(null);
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
        return 'Obstrucción en Vía';
      case 'otro':
        return 'Anomalía / Otro';
      default:
        return tipo;
    }
  };

  const getTypeBadgeClass = (tipo: string) => {
    switch (tipo) {
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

  return (
    <div className="card incident-log-card">
      <div className="card-header incident-header-wrap">
        <div className="card-title-group">
          <AlertOctagon className="card-icon text-red" />
          <div>
            <h2 className="card-title">REGISTRO DE INCIDENTES Y ANOMALÍAS EN VÍA (SQLITE)</h2>
            <p className="card-subtitle-text">
              Persistencia real en SQLite (<code>/api/v1/incidentes</code>) con actualización en vivo por WebSocket
            </p>
          </div>
        </div>

        <div className="filter-group" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <Filter size={14} className="text-cyan inline mr-1" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="filter-select"
              title="Filtrar por categoría vial"
            >
              <option value="all">Todas las anomalías</option>
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
            title="Filtrar por estado operativo"
          >
            <option value="all">Todos los estados</option>
            <option value="reportado">Reportado</option>
            <option value="en_revision">En Revisión</option>
            <option value="atendido">Atendido</option>
            <option value="descartado">Descartado</option>
          </select>

          <button
            type="button"
            className="btn btn-outline btn-refresh-incidents"
            onClick={fetchIncidents}
            disabled={isLoading}
            title="Recargar incidentes desde SQLite"
          >
            <RefreshCw size={14} className={isLoading ? 'spin-icon' : ''} />
            <span>Actualizar</span>
          </button>
        </div>
      </div>

      {/* Action or Network Error Banner */}
      {(errorMessage || actionError) && (
        <div className="alert-banner alert-banner-error" style={{ marginTop: '0.75rem' }}>
          <AlertTriangle size={18} className="text-red flex-shrink-0" />
          <div className="alert-content" style={{ flex: 1 }}>
            <strong>Error de comunicación con SQLite API:</strong> {errorMessage || actionError}
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '0.3rem 0.7rem', fontSize: '0.75rem' }}
            onClick={() => {
              setActionError(null);
              fetchIncidents();
            }}
          >
            <RefreshCw size={13} /> Reintentar
          </button>
        </div>
      )}

      <div className="incidents-table-wrapper">
        {isLoading && mergedIncidents.length === 0 ? (
          <div className="empty-state">
            <div className="spinner-medium text-cyan" />
            <p>Consultando incidentes almacenados en SQLite...</p>
          </div>
        ) : mergedIncidents.length === 0 ? (
          <div className="empty-state">
            {errorMessage ? (
              <>
                <AlertTriangle size={32} className="text-amber opacity-80" />
                <p>No se pudieron cargar los incidentes porque el backend no está disponible.</p>
              </>
            ) : (
              <>
                <CheckCircle size={32} className="text-green opacity-70" />
                <p>No hay incidentes registrados en SQLite que coincidan con los filtros seleccionados.</p>
              </>
            )}
          </div>
        ) : (
          <table className="incidents-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>FECHA / HORA</th>
                <th>ORIGEN</th>
                <th>CATEGORÍA</th>
                <th>SEVERIDAD</th>
                <th>UBICACIÓN 3D</th>
                <th>DESCRIPCIÓN</th>
                <th>ESTADO</th>
              </tr>
            </thead>
            <tbody>
              {mergedIncidents.map((inc) => (
                <tr key={inc.id} className={`incident-row incident-sev-${inc.severidad}`}>
                  <td className="inc-id">#{inc.id}</td>
                  <td className="inc-time" title={inc.timestamp}>
                    <Clock size={12} className="inline mr-1 opacity-70" />
                    {new Date(inc.timestamp).toLocaleTimeString()}
                  </td>
                  <td>
                    <span className="drone-origin-tag">{inc.drone_id}</span>
                  </td>
                  <td>
                    <span className={`class-badge ${getTypeBadgeClass(inc.tipo)}`}>
                      {getTypeName(inc.tipo)}
                    </span>
                  </td>
                  <td>
                    <span className={`severity-pill ${getSeverityBadge(inc.severidad)}`}>
                      {inc.severidad.toUpperCase()}
                    </span>
                  </td>
                  <td className="inc-coords">
                    {inc.pos_x != null && inc.pos_y != null && inc.pos_z != null ? (
                      <span
                        title={`Coordenadas en marco: ${
                          inc.coordenadas_tipo || 'simulacion_webots'
                        }`}
                      >
                        [{inc.pos_x.toFixed(1)}, {inc.pos_y.toFixed(1)}, {inc.pos_z.toFixed(1)}m]
                      </span>
                    ) : (
                      <span className="opacity-50 italic">Sin posición</span>
                    )}
                  </td>
                  <td className="inc-desc" title={inc.descripcion}>
                    {inc.descripcion}
                    {inc.confidence > 0 && (
                      <span className="inc-conf-badge">
                        {(inc.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </td>
                  <td>
                    <select
                      value={inc.estado}
                      disabled={updatingId === inc.id || !isApiOnline}
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
