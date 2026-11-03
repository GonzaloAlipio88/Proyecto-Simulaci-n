import React, { useState, useMemo } from 'react';
import { Map, Navigation, MapPin, AlertTriangle, Crosshair, Compass, Gauge } from 'lucide-react';
import type { TelemetryData, Incidente, MissionWaypoint } from '../types';

interface RoadMap2DProps {
  telemetry: TelemetryData | null;
  telemetryHistory: TelemetryData[];
  waypoints: MissionWaypoint[];
  incidents: Incidente[];
  droneId: string;
}

const DEFAULT_WAYPOINTS: MissionWaypoint[] = [
  { index: 1, x: 0.0, y: -30.0, z: 6.0, hover_time: 2.0, name: 'WP1', description: 'Tramo Sur (-30m)' },
  { index: 2, x: 0.0, y: -15.0, z: 6.0, hover_time: 2.0, name: 'WP2', description: 'Tramo Centro-Sur (-15m)' },
  { index: 3, x: 0.0, y: 0.0, z: 6.0, hover_time: 3.0, name: 'WP3', description: 'Intersección Central (0m)' },
  { index: 4, x: 0.0, y: 15.0, z: 6.0, hover_time: 2.0, name: 'WP4', description: 'Tramo Centro-Norte (+15m)' },
  { index: 5, x: 0.0, y: 30.0, z: 6.0, hover_time: 2.0, name: 'WP5', description: 'Tramo Norte (+30m)' }
];

// Simulation world bounds (inspection_zone.wbt)
// Longitudinal road axis: Y in [-52m, +52m] -> mapped horizontally on SVG [50..630]
// Lateral road axis: X in [-12m, +12m] -> mapped vertically on SVG [205..35]
const WORLD_Y_MIN = -52;
const WORLD_Y_MAX = 52;
const WORLD_X_MIN = -12;
const WORLD_X_MAX = 12;

const SVG_LEFT = 50;
const SVG_RIGHT = 630;
const SVG_TOP = 35;
const SVG_BOTTOM = 205;

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

function worldToSvg(posX: number, posY: number): { sx: number; sy: number } {
  const cy = clamp(posY, WORLD_Y_MIN, WORLD_Y_MAX);
  const cx = clamp(posX, WORLD_X_MIN, WORLD_X_MAX);
  const ratioY = (cy - WORLD_Y_MIN) / (WORLD_Y_MAX - WORLD_Y_MIN);
  const ratioX = (cx - WORLD_X_MIN) / (WORLD_X_MAX - WORLD_X_MIN);
  const sx = SVG_LEFT + ratioY * (SVG_RIGHT - SVG_LEFT);
  const sy = SVG_BOTTOM - ratioX * (SVG_BOTTOM - SVG_TOP);
  return { sx: Number(sx.toFixed(1)), sy: Number(sy.toFixed(1)) };
}

function getIncidentColor(tipo: Incidente['tipo']): string {
  switch (tipo) {
    case 'poste_luz':
      return '#00b4d8';
    case 'vegetacion_invasiva':
      return '#2ec4b6';
    case 'obstruccion_via':
      return '#e71d36';
    default:
      return '#f59e0b';
  }
}

function getIncidentLabel(tipo: Incidente['tipo']): string {
  switch (tipo) {
    case 'poste_luz':
      return 'Poste de Alumbrado';
    case 'vegetacion_invasiva':
      return 'Vegetación Invasiva';
    case 'obstruccion_via':
      return 'Obstáculo en Vía';
    default:
      return 'Otro';
  }
}

export const RoadMap2D: React.FC<RoadMap2DProps> = ({
  telemetry,
  telemetryHistory,
  waypoints,
  incidents,
  droneId
}) => {
  const [selectedIncident, setSelectedIncident] = useState<Incidente | null>(null);

  const missionWps = waypoints.length > 0 ? waypoints : DEFAULT_WAYPOINTS;

  // Filter ONLY incidents that have real coordinates (pos_x and pos_y present)
  const geoIncidents = useMemo(() => {
    return incidents.filter(
      (inc) =>
        inc.pos_x !== null &&
        inc.pos_x !== undefined &&
        inc.pos_y !== null &&
        inc.pos_y !== undefined &&
        inc.estado !== 'descartado'
    );
  }, [incidents]);

  const unlocatedIncidentsCount = useMemo(() => {
    return incidents.filter(
      (inc) =>
        (inc.pos_x === null || inc.pos_x === undefined || inc.pos_y === null || inc.pos_y === undefined) &&
        inc.estado !== 'descartado'
    ).length;
  }, [incidents]);

  // Build chronological trajectory points including latest telemetry
  const trajectoryPoints = useMemo(() => {
    const ordered = [...telemetryHistory].reverse();
    if (telemetry) {
      const last = ordered[ordered.length - 1];
      if (!last || last.pos_x !== telemetry.pos_x || last.pos_y !== telemetry.pos_y) {
        ordered.push(telemetry);
      }
    }
    return ordered;
  }, [telemetryHistory, telemetry]);

  const polylineAttr = useMemo(() => {
    return trajectoryPoints
      .map((pt) => {
        const { sx, sy } = worldToSvg(pt.pos_x, pt.pos_y);
        return `${sx},${sy}`;
      })
      .join(' ');
  }, [trajectoryPoints]);

  const homeSvg = worldToSvg(0.0, -45.0);
  const roadTopEdge = worldToSvg(3.0, 0).sy;
  const roadBottomEdge = worldToSvg(-3.0, 0).sy;
  const roadCenterY = worldToSvg(0.0, 0).sy;
  const roadLeftEdge = worldToSvg(0, -50.0).sx;
  const roadRightEdge = worldToSvg(0, 50.0).sx;

  const dronePos = telemetry
    ? worldToSvg(telemetry.pos_x, telemetry.pos_y)
    : null;

  const activeWpIndex = telemetry?.current_waypoint ?? null;

  // Real drone heading, horizontal velocity vector & flight state dynamics (Semana 11)
  const droneDynamics = useMemo(() => {
    if (!telemetry) return null;

    const speed = Math.max(0, telemetry.speed ?? 0);
    const flightMode = (telemetry.flight_mode ?? '').toUpperCase();
    const isHover = flightMode.includes('HOVER');
    const isGround = flightMode.includes('GROUND') || flightMode.includes('LANDED');
    const isReturning = flightMode.includes('RETURN') || flightMode.includes('RTL') || flightMode.includes('RTH');
    const isNavigating = flightMode.includes('NAV') || flightMode.includes('TAKEOFF');

    // Direction calculation:
    // Determine displacement delta from previous telemetry points if available
    let headingDeg = 0;
    const hasMovement = speed > 0.15;

    if (trajectoryPoints.length >= 2) {
      const curr = trajectoryPoints[trajectoryPoints.length - 1];
      const prev = trajectoryPoints[trajectoryPoints.length - 2];
      const dx = curr.pos_x - prev.pos_x; // Lateral world (+X = up on SVG)
      const dy = curr.pos_y - prev.pos_y; // Longitudinal world (+Y = right on SVG)
      const dist = Math.hypot(dx, dy);
      if (dist > 0.05) {
        // In SVG coordinates: +dy is +X_svg (right), +dx is -Y_svg (up)
        // atan2(dy_svg, dx_svg) = atan2(-dx, dy)
        headingDeg = (Math.atan2(-dx, dy) * 180) / Math.PI;
      } else if (telemetry.yaw !== undefined && telemetry.yaw !== null) {
        // Fallback to yaw orientation if stationary
        headingDeg = ((-telemetry.yaw) * 180) / Math.PI;
      }
    } else if (telemetry.yaw !== undefined && telemetry.yaw !== null) {
      headingDeg = ((-telemetry.yaw) * 180) / Math.PI;
    }

    if (isReturning && !hasMovement) {
      headingDeg = 180; // Facing south towards base
    }

    // Vector length proportional to real speed (14px min to 46px max)
    const vectorLength = isHover || isGround ? 0 : Math.min(46, Math.max(14, 12 + speed * 6.8));
    const rad = (headingDeg * Math.PI) / 180;
    const targetVectorX = Number((Math.cos(rad) * vectorLength).toFixed(1));
    const targetVectorY = Number((Math.sin(rad) * vectorLength).toFixed(1));

    return {
      speed,
      headingDeg: Math.round(((headingDeg % 360) + 360) % 360),
      vectorLength,
      targetVectorX,
      targetVectorY,
      isHover,
      isGround,
      isReturning,
      isNavigating,
      hasMovement,
      flightMode
    };
  }, [telemetry, trajectoryPoints]);

  return (
    <div className="card roadmap-card">
      <div className="card-header">
        <div className="card-title-group">
          <Map className="card-icon text-cyan" />
          <h2 className="card-title">MAPA TÁCTICO 2D DEL CORREDOR VIAL (WEBOTS)</h2>
        </div>
        <div className="roadmap-badges">
          <span className="count-pill" title="Waypoints de la misión de patrullaje">
            <MapPin size={12} /> {missionWps.length} Waypoints
          </span>
          <span className="count-pill" title="Puntos registrados en trayectoria histórica">
            <Navigation size={12} /> {trajectoryPoints.length} Ptos. Ruta
          </span>
          <span className="count-pill" title="Incidentes con coordenadas reales de simulación">
            <AlertTriangle size={12} /> {geoIncidents.length} Incidentes en Mapa
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="roadmap-legend">
        <div className="legend-item">
          <span className="roadmap-dot roadmap-dot-drone" />
          <span>Dron ({droneId})</span>
        </div>
        <div className="legend-item">
          <span className="roadmap-dot roadmap-dot-wp" />
          <span>Waypoints (WP1–WP5)</span>
        </div>
        <div className="legend-item">
          <span className="roadmap-line-sample" />
          <span>Trayectoria Histórica</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator legend-pole" />
          <span>Poste</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator legend-veg" />
          <span>Vegetación</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator legend-obs" />
          <span>Obstáculo</span>
        </div>
        {unlocatedIncidentsCount > 0 && (
          <div className="roadmap-unlocated-note" title="Incidentes provenientes de carga manual de imágenes sin coordenadas">
            ({unlocatedIncidentsCount} sin coord. omitidos)
          </div>
        )}
      </div>

      {/* 2D SVG Map Viewport */}
      <div className="roadmap-svg-wrapper">
        <svg
          viewBox="0 0 680 240"
          className="roadmap-svg"
          role="img"
          aria-label="Mapa 2D del corredor vial de inspección"
        >
          <defs>
            <linearGradient id="roadSurfaceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1e293b" />
              <stop offset="50%" stopColor="#0f172a" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
            <marker
              id="velocityArrow"
              markerWidth="7"
              markerHeight="7"
              refX="5"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 7 3.5, 0 7" fill="#38bdf8" />
            </marker>
            <marker
              id="velocityArrowRth"
              markerWidth="7"
              markerHeight="7"
              refX="5"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 7 3.5, 0 7" fill="#f59e0b" />
            </marker>
          </defs>

          {/* Coordinate Grid Lines along Y (-45, -30, -15, 0, 15, 30, 45) */}
          {[-45, -30, -15, 0, 15, 30, 45].map((yVal) => {
            const { sx } = worldToSvg(0, yVal);
            return (
              <g key={`grid-y-${yVal}`}>
                <line
                  x1={sx}
                  y1={SVG_TOP}
                  x2={sx}
                  y2={SVG_BOTTOM}
                  stroke="rgba(148, 163, 184, 0.12)"
                  strokeDasharray="3 3"
                />
                <text
                  x={sx}
                  y={SVG_BOTTOM + 16}
                  textAnchor="middle"
                  fill="#64748b"
                  fontSize="9"
                  fontFamily="monospace"
                >
                  Y={yVal}m
                </text>
              </g>
            );
          })}

          {/* Lateral X Axis Labels */}
          {[-10, 0, 10].map((xVal) => {
            const { sy } = worldToSvg(xVal, 0);
            return (
              <g key={`grid-x-${xVal}`}>
                <line
                  x1={SVG_LEFT}
                  y1={sy}
                  x2={SVG_RIGHT}
                  y2={sy}
                  stroke="rgba(148, 163, 184, 0.08)"
                />
                <text
                  x={SVG_LEFT - 6}
                  y={sy + 3}
                  textAnchor="end"
                  fill="#64748b"
                  fontSize="9"
                  fontFamily="monospace"
                >
                  X={xVal}m
                </text>
              </g>
            );
          })}

          {/* Road Corridor Surface (Y: -50m to +50m, X: -3m to +3m) */}
          <rect
            x={roadLeftEdge}
            y={roadTopEdge}
            width={roadRightEdge - roadLeftEdge}
            height={roadBottomEdge - roadTopEdge}
            fill="url(#roadSurfaceGrad)"
            stroke="rgba(148, 163, 184, 0.35)"
            strokeWidth="1.5"
            rx="4"
          />

          {/* Road Center Divided Line (X = 0) */}
          <line
            x1={roadLeftEdge + 6}
            y1={roadCenterY}
            x2={roadRightEdge - 6}
            y2={roadCenterY}
            stroke="rgba(250, 204, 21, 0.45)"
            strokeWidth="1.5"
            strokeDasharray="8 6"
          />

          {/* Planned Mission Waypoint Connector Line */}
          {missionWps.length > 1 && (
            <polyline
              fill="none"
              stroke="rgba(56, 189, 248, 0.25)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              points={[
                `${homeSvg.sx},${homeSvg.sy}`,
                ...missionWps.map((wp) => {
                  const p = worldToSvg(wp.x, wp.y);
                  return `${p.sx},${p.sy}`;
                })
              ].join(' ')}
            />
          )}

          {/* Home Base Helipad (X=0, Y=-45m) */}
          <g transform={`translate(${homeSvg.sx}, ${homeSvg.sy})`}>
            <circle r="10" fill="rgba(16, 185, 129, 0.18)" stroke="#10b981" strokeWidth="1.5" />
            <text
              x="0"
              y="3.5"
              textAnchor="middle"
              fill="#10b981"
              fontSize="10"
              fontWeight="bold"
              fontFamily="monospace"
            >
              H
            </text>
            <text
              x="0"
              y="-14"
              textAnchor="middle"
              fill="#10b981"
              fontSize="8.5"
              fontFamily="monospace"
            >
              BASE
            </text>
          </g>

          {/* Historical Trajectory Polyline & Sample Nodes */}
          {trajectoryPoints.length > 1 && (
            <polyline
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={polylineAttr}
              opacity="0.85"
            />
          )}
          {trajectoryPoints.map((pt, idx) => {
            const { sx, sy } = worldToSvg(pt.pos_x, pt.pos_y);
            return (
              <circle
                key={`traj-pt-${pt.id ?? idx}`}
                cx={sx}
                cy={sy}
                r="2.2"
                fill="#38bdf8"
                opacity="0.65"
              >
                <title>
                  {` Muestra #${idx + 1}: X=${pt.pos_x.toFixed(1)}m, Y=${pt.pos_y.toFixed(1)}m, Z=${pt.pos_z.toFixed(1)}m (${pt.flight_mode})`}
                </title>
              </circle>
            );
          })}

          {/* Mission Waypoints (WP1 - WP5) */}
          {missionWps.map((wp) => {
            const { sx, sy } = worldToSvg(wp.x, wp.y);
            const isActive = activeWpIndex === wp.index;
            const isVisited = activeWpIndex !== null && wp.index < activeWpIndex;
            const strokeColor = isActive ? '#facc15' : isVisited ? '#10b981' : '#94a3b8';
            const fillColor = isActive
              ? 'rgba(250, 204, 21, 0.25)'
              : isVisited
              ? 'rgba(16, 185, 129, 0.2)'
              : 'rgba(30, 41, 59, 0.85)';

            return (
              <g key={`wp-${wp.index}`} transform={`translate(${sx}, ${sy})`}>
                <circle
                  r={isActive ? 8 : 6.5}
                  fill={fillColor}
                  stroke={strokeColor}
                  strokeWidth={isActive ? '2' : '1.4'}
                />
                <text
                  x="0"
                  y="-11"
                  textAnchor="middle"
                  fill={isActive ? '#facc15' : '#cbd5e1'}
                  fontSize="9"
                  fontWeight="bold"
                  fontFamily="monospace"
                >
                  {wp.name}
                </text>
                <title>{`${wp.name}: ${wp.description} (X=${wp.x}m, Y=${wp.y}m, Z=${wp.z}m)`}</title>
              </g>
            );
          })}

          {/* Detected Incidents with Real Coordinates */}
          {geoIncidents.map((inc, idx) => {
            const { sx, sy } = worldToSvg(inc.pos_x ?? 0, inc.pos_y ?? 0);
            // Slight vertical stagger if multiple incidents share Y on X=0 so all markers remain clickable
            const offsetY = (idx % 2 === 0 ? -1 : 1) * (inc.pos_x === 0 ? 14 : 0);
            const markerColor = getIncidentColor(inc.tipo);
            const isSelected = selectedIncident?.id === inc.id;

            return (
              <g
                key={`inc-marker-${inc.id}`}
                transform={`translate(${sx}, ${sy + offsetY})`}
                className="roadmap-incident-marker"
                onClick={() => setSelectedIncident(isSelected ? null : inc)}
              >
                {isSelected && (
                  <circle
                    r="11"
                    fill="none"
                    stroke="#ffffff"
                    strokeWidth="1.5"
                    strokeDasharray="2 2"
                  />
                )}
                <polygon
                  points="0,-7 6.5,5 -6.5,5"
                  fill={markerColor}
                  stroke="#0f172a"
                  strokeWidth="1.2"
                />
                <text
                  x="0"
                  y="14"
                  textAnchor="middle"
                  fill={markerColor}
                  fontSize="8"
                  fontWeight="bold"
                  fontFamily="monospace"
                >
                  #{inc.id}
                </text>
                <title>
                  {`Incidente #${inc.id} - ${getIncidentLabel(inc.tipo)} (${inc.severidad.toUpperCase()}) | Pos: (${inc.pos_x?.toFixed(1)}, ${inc.pos_y?.toFixed(1)}, ${inc.pos_z?.toFixed(1)}m)`}
                </title>
              </g>
            );
          })}

          {/* Live Drone Position, Velocity Vector & Heading Indicator (Semana 11) */}
          {dronePos && telemetry && droneDynamics && (
            <g transform={`translate(${dronePos.sx}, ${dronePos.sy})`}>
              {/* Velocity Vector Line with Arrowhead */}
              {droneDynamics.vectorLength > 0 && (
                <line
                  x1="0"
                  y1="0"
                  x2={droneDynamics.targetVectorX}
                  y2={droneDynamics.targetVectorY}
                  stroke={droneDynamics.isReturning ? '#f59e0b' : '#38bdf8'}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  markerEnd={
                    droneDynamics.isReturning ? 'url(#velocityArrowRth)' : 'url(#velocityArrow)'
                  }
                />
              )}

              {/* Hover active position damping ring */}
              {droneDynamics.isHover && (
                <circle
                  r="16"
                  fill="rgba(16, 185, 129, 0.16)"
                  stroke="#10b981"
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                />
              )}

              {/* Outer halo */}
              <circle
                r={droneDynamics.isHover ? 12 : 10}
                fill={
                  droneDynamics.isHover
                    ? 'rgba(16, 185, 129, 0.22)'
                    : droneDynamics.isReturning
                    ? 'rgba(245, 158, 11, 0.22)'
                    : 'rgba(56, 189, 248, 0.22)'
                }
                stroke={
                  droneDynamics.isHover
                    ? 'rgba(16, 185, 129, 0.6)'
                    : droneDynamics.isReturning
                    ? 'rgba(245, 158, 11, 0.6)'
                    : 'rgba(56, 189, 248, 0.6)'
                }
                strokeWidth="1"
              />

              {/* Drone center core */}
              <circle
                r="5.5"
                fill={
                  droneDynamics.isHover
                    ? '#10b981'
                    : droneDynamics.isReturning
                    ? '#f59e0b'
                    : '#38bdf8'
                }
                stroke="#ffffff"
                strokeWidth="1.6"
              />

              {/* Dynamic Speed & Flight Mode Badge directly above/below */}
              <g transform="translate(0, -17)">
                <rect
                  x="-32"
                  y="-8.5"
                  width="64"
                  height="15"
                  rx="7.5"
                  fill="rgba(15, 23, 42, 0.88)"
                  stroke={
                    droneDynamics.isHover
                      ? '#10b981'
                      : droneDynamics.isReturning
                      ? '#f59e0b'
                      : '#38bdf8'
                  }
                  strokeWidth="1"
                />
                <text
                  x="0"
                  y="2.5"
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="8"
                  fontWeight="bold"
                  fontFamily="monospace"
                >
                  {droneDynamics.isHover
                    ? 'HOVER (0 m/s)'
                    : droneDynamics.isGround
                    ? 'TIERRA (0 m/s)'
                    : `${droneDynamics.speed.toFixed(1)} m/s`}
                </text>
              </g>

              {/* Drone coordinate label */}
              <text
                x="0"
                y="20"
                textAnchor="middle"
                fill="#94a3b8"
                fontSize="8"
                fontWeight="bold"
                fontFamily="monospace"
              >
                {`(${telemetry.pos_x.toFixed(1)}, ${telemetry.pos_y.toFixed(1)}m)`}
              </text>
              <title>
                {`Dron ${droneId}: X=${telemetry.pos_x.toFixed(2)}m, Y=${telemetry.pos_y.toFixed(2)}m, Z=${telemetry.pos_z.toFixed(2)}m | Vel: ${droneDynamics.speed.toFixed(2)} m/s | Rumbo: ${droneDynamics.headingDeg}° | Modo: ${telemetry.flight_mode}`}
              </title>
            </g>
          )}
        </svg>
      </div>

      {/* Selected Incident Detail or Live Drone Summary Bar */}
      <div className="roadmap-footer-bar">
        {selectedIncident ? (
          <div className="roadmap-selected-incident">
            <span className="roadmap-selected-badge">
              Incidente #{selectedIncident.id}: {getIncidentLabel(selectedIncident.tipo)}
            </span>
            <span className="mono-text">
              Pos: ({selectedIncident.pos_x?.toFixed(1)}, {selectedIncident.pos_y?.toFixed(1)},{' '}
              {(selectedIncident.pos_z ?? 0).toFixed(1)}m) | Severidad:{' '}
              <strong>{selectedIncident.severidad.toUpperCase()}</strong> | Estado:{' '}
              <strong>{selectedIncident.estado}</strong>
            </span>
            <button
              type="button"
              className="btn-clear-map-selection"
              onClick={() => setSelectedIncident(null)}
            >
              Cerrar detalle
            </button>
          </div>
        ) : (
          <div className="roadmap-status-summary">
            <span className="roadmap-coord-pill">
              <Crosshair size={13} className="text-cyan" />
              {telemetry
                ? `Pos: X=${telemetry.pos_x.toFixed(2)}m | Y=${telemetry.pos_y.toFixed(2)}m | Z=${telemetry.pos_z.toFixed(2)}m`
                : 'Esperando telemetría de posición desde Webots...'}
            </span>
            {droneDynamics && (
              <>
                <span className="roadmap-coord-pill" title="Velocidad horizontal real del dron">
                  <Gauge size={13} className="text-cyan" />
                  {`Vel: ${droneDynamics.speed.toFixed(2)} m/s`}
                </span>
                <span className="roadmap-coord-pill" title="Rumbo y vector de desplazamiento hacia waypoints">
                  <Compass size={13} className="text-cyan" />
                  {`Rumbo: ${droneDynamics.headingDeg}° (${droneDynamics.flightMode})`}
                </span>
              </>
            )}
            <span className="roadmap-hint">
              Haga clic en un marcador de incidente (▲) en el mapa para inspeccionar su ubicación exacta.
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

