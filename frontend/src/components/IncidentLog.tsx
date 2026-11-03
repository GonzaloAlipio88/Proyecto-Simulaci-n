import { useState, useEffect, useCallback, useMemo, type FC } from 'react';
import {
  AlertOctagon,
  Filter,
  CheckCircle,
  Clock,
  Image as ImageIcon,
  Trash2,
  RefreshCw,
  Search,
  AlertTriangle,
  Database,
  ExternalLink,
  X
} from 'lucide-react';
import type { Incidente, IncidenteStats } from '../types';
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
  const [stats, setStats] = useState<IncidenteStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [onlyWithImage, setOnlyWithImage] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');

  const [previewIncident, setPreviewIncident] = useState<Incidente | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Debounce search text
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const loadIncidentsAndStats = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const filters: {
        tipo?: string;
        severidad?: string;
        estado?: string;
        search?: string;
        has_image?: boolean;
        limit?: number;
      } = { limit: 100 };

      if (typeFilter !== 'all') filters.tipo = typeFilter;
      if (severityFilter !== 'all') filters.severidad = severityFilter;
      if (statusFilter !== 'all') filters.estado = statusFilter;
      if (debouncedSearch) filters.search = debouncedSearch;
      if (onlyWithImage) filters.has_image = true;

      const [data, statsData] = await Promise.all([
        api.getIncidentes(filters),
        api.getIncidentStats()
      ]);

      setIncidents(data);
      if (statsData) {
        setStats(statsData);
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Error al consultar el historial de incidentes en SQLite.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [typeFilter, severityFilter, statusFilter, debouncedSearch, onlyWithImage]);

  // Reload when filters change or when backend comes back online
  useEffect(() => {
    let active = true;
    const triggerLoad = async () => {
      if (!active) return;
      await loadIncidentsAndStats();
    };
    triggerLoad();
    return () => {
      active = false;
    };
  }, [loadIncidentsAndStats, isApiOnline]);

  // Refresh stats helper
  const refreshStatsQuietly = useCallback(async () => {
    const statsData = await api.getIncidentStats();
    if (statsData) {
      setStats(statsData);
    }
  }, []);

  // Merge incoming live / newly created / updated / deleted incidents
  const mergedIncidents = useMemo(() => {
    let list = [...incidents];

    const upsertItem = (item: Incidente | null) => {
      if (!item) return;
      // Check if it matches active filters
      if (typeFilter !== 'all' && item.tipo !== typeFilter) return;
      if (severityFilter !== 'all' && item.severidad !== severityFilter) return;
      if (statusFilter !== 'all' && item.estado !== statusFilter) return;
      if (onlyWithImage && !item.imagen_id) return;
      if (
        debouncedSearch &&
        !item.descripcion.toLowerCase().includes(debouncedSearch.toLowerCase())
      ) {
        return;
      }

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
    statusFilter,
    onlyWithImage,
    debouncedSearch
  ]);

  // Refresh stats when WebSocket or manual incident events happen
  useEffect(() => {
    if (latestWsIncident || latestUpdatedIncident || latestDeletedIncident || newlyCreatedIncident) {
      const timer = window.setTimeout(() => {
        refreshStatsQuietly();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [
    latestWsIncident,
    latestUpdatedIncident,
    latestDeletedIncident,
    newlyCreatedIncident,
    refreshStatsQuietly
  ]);

  const handleStatusChange = async (id: number, newStatus: string) => {
    setUpdatingId(id);
    setActionError(null);
    try {
      const updated = await api.updateIncidente(id, { estado: newStatus });
      setIncidents((prev) => prev.map((i) => (i.id === id ? updated : i)));
      await refreshStatsQuietly();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `No se pudo actualizar el incidente #${id}`;
      setActionError(msg);
    } finally {
      setUpdatingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm(`¿Está seguro de eliminar permanentemente el incidente #${id} de SQLite?`)) {
      return;
    }
    setDeletingId(id);
    setActionError(null);
    try {
      await api.deleteIncidente(id);
      setIncidents((prev) => prev.filter((i) => i.id !== id));
      if (previewIncident?.id === id) {
        setPreviewIncident(null);
      }
      await refreshStatsQuietly();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `No se pudo eliminar el incidente #${id}`;
      setActionError(msg);
    } finally {
      setDeletingId(null);
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
              Persistencia real en SQLite (<code>/api/v1/incidentes</code>) con deduplicación espacio-temporal y actualización en vivo por WebSocket
            </p>
          </div>
        </div>

        <div className="filter-group" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {/* Search box */}
          <div className="incident-search-box">
            <Search size={13} className="text-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar en descripción..."
              className="incident-search-input"
            />
            {searchQuery && (
              <button
                type="button"
                className="btn-clear-search"
                onClick={() => setSearchQuery('')}
                title="Limpiar búsqueda"
              >
                <X size={12} />
              </button>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center' }}>
            <Filter size={14} className="text-cyan inline mr-1" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="filter-select"
              title="Filtrar por categoría vial"
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
            title="Filtrar por estado operativo"
          >
            <option value="all">Todos los estados</option>
            <option value="reportado">Reportado</option>
            <option value="en_revision">En Revisión</option>
            <option value="atendido">Atendido</option>
            <option value="descartado">Descartado</option>
          </select>

          <label className="filter-checkbox-label" title="Mostrar solo incidentes con imagen vinculada">
            <input
              type="checkbox"
              checked={onlyWithImage}
              onChange={(e) => setOnlyWithImage(e.target.checked)}
            />
            <span>Con foto</span>
          </label>

          <button
            type="button"
            className="btn btn-outline btn-refresh-incidents"
            onClick={loadIncidentsAndStats}
            disabled={isLoading}
            title="Recargar incidentes y estadísticas desde SQLite"
          >
            <RefreshCw size={14} className={isLoading ? 'spin-icon' : ''} />
            <span>Actualizar</span>
          </button>
        </div>
      </div>

      {/* SQLite Aggregate Stats Bar (GET /api/v1/incidentes/stats) */}
      {stats && (
        <div className="incident-stats-bar">
          <div className="stat-pill">
            <Database size={13} className="text-cyan" />
            <span>Total en SQLite:</span>
            <strong>{stats.total_incidentes}</strong>
          </div>
          <div className="stat-pill stat-pill-pole">
            <span className="legend-indicator legend-pole"></span>
            <span>Postes:</span>
            <strong>{stats.por_tipo.poste_luz ?? 0}</strong>
          </div>
          <div className="stat-pill stat-pill-veg">
            <span className="legend-indicator legend-veg"></span>
            <span>Vegetación:</span>
            <strong>{stats.por_tipo.vegetacion_invasiva ?? 0}</strong>
          </div>
          <div className="stat-pill stat-pill-obs">
            <span className="legend-indicator legend-obs"></span>
            <span>Obstrucciones:</span>
            <strong>{stats.por_tipo.obstruccion_via ?? 0}</strong>
          </div>
          <div className="stat-pill">
            <span>Críticos / Altos:</span>
            <strong className="text-red">
              {(stats.por_severidad.critica ?? 0) + (stats.por_severidad.alta ?? 0)}
            </strong>
          </div>
          <div className="stat-pill">
            <span>Atendidos:</span>
            <strong className="text-green">{stats.por_estado.atendido ?? 0}</strong>
          </div>
          <div className="stat-pill">
            <span>Con Evidencia:</span>
            <strong>{stats.con_imagen}</strong>
          </div>
          <div className="stat-pill">
            <span>Confianza Promedio:</span>
            <strong className="text-amber">{(stats.confianza_promedio * 100).toFixed(1)}%</strong>
          </div>
        </div>
      )}

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
              loadIncidentsAndStats();
            }}
          >
            <RefreshCw size={13} /> Reintentar
          </button>
        </div>
      )}

      {/* Inline Image Preview Drawer if an incident image is selected */}
      {previewIncident && previewIncident.imagen_id && (
        <div className="incident-image-preview-panel">
          <div className="preview-panel-header">
            <div className="flex items-center gap-2">
              <ImageIcon size={16} className="text-cyan" />
              <strong>
                Evidencia Fotográfica · Incidente #{previewIncident.id} (Imagen #
                {previewIncident.imagen_id})
              </strong>
              <span className={`class-badge ${getTypeBadgeClass(previewIncident.tipo)}`}>
                {getTypeName(previewIncident.tipo)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={api.getIncidentImageUrl(previewIncident.id, true)}
                target="_blank"
                rel="noreferrer"
                className="btn-toggle-view"
                style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
              >
                <ExternalLink size={12} /> Abrir original
              </a>
              <button
                type="button"
                className="btn-toggle-view"
                onClick={() => setPreviewIncident(null)}
              >
                <X size={13} /> Cerrar vista
              </button>
            </div>
          </div>
          <div className="preview-panel-body">
            <img
              src={api.getIncidentImageUrl(previewIncident.id, true)}
              alt={`Evidencia del incidente #${previewIncident.id}`}
              className="preview-panel-img"
            />
            <div className="preview-panel-meta">
              <p>
                <strong>Descripción:</strong> {previewIncident.descripcion}
              </p>
              <p>
                <strong>Dron / Fuente:</strong> {previewIncident.drone_id} ·{' '}
                <strong>Confianza:</strong> {(previewIncident.confidence * 100).toFixed(1)}% ·{' '}
                <strong>Fecha:</strong> {new Date(previewIncident.timestamp).toLocaleString()}
              </p>
            </div>
          </div>
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
                <th>DESCRIPCIÓN & CONFIANZA</th>
                <th>IMAGEN</th>
                <th>ESTADO</th>
                <th>ACCIONES</th>
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
                  <td className="inc-image-cell">
                    {inc.imagen_id ? (
                      <div className="inc-image-actions">
                        <button
                          type="button"
                          className="incident-image-btn"
                          onClick={() =>
                            setPreviewIncident(
                              previewIncident?.id === inc.id ? null : inc
                            )
                          }
                          title="Previsualizar fotografía vinculada a este incidente"
                        >
                          <ImageIcon size={13} />
                          <span>#{inc.imagen_id}</span>
                        </button>
                        <a
                          href={api.getIncidentImageUrl(inc.id, true)}
                          target="_blank"
                          rel="noreferrer"
                          title="Abrir o descargar imagen en pestaña nueva"
                          className="incident-image-ext"
                        >
                          <ExternalLink size={12} />
                        </a>
                      </div>
                    ) : (
                      <span className="opacity-40 italic" style={{ fontSize: '0.78rem' }}>
                        Sin foto
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
                  <td>
                    <button
                      type="button"
                      disabled={deletingId === inc.id || !isApiOnline}
                      onClick={() => handleDelete(inc.id)}
                      title="Eliminar incidente de la base de datos SQLite"
                      className="btn-delete-incident"
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
