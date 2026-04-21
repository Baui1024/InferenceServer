import { useCallback, useRef, useState, useEffect } from 'react';
import type { ZoneConfig, ZoneStateInfo } from '../types/camera';

interface Props {
  zones: ZoneConfig[];
  zoneStates: ZoneStateInfo[];
  /** Called with updated zones array after any edit */
  onUpdate: (zones: ZoneConfig[]) => void;
  /** SVG interactivity enabled (only when automation tab is active) */
  interactive: boolean;
  /** Container width in px */
  width: number;
  /** Container height in px */
  height: number;
}

export default function ZoneOverlay({ zones, zoneStates, onUpdate, interactive, width, height }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dragging, setDragging] = useState<{ zoneIdx: number; pointIdx: number } | null>(null);
  const [hovered, setHovered] = useState<{ zoneIdx: number; pointIdx: number } | null>(null);

  // Convert normalised 0-1 coords to pixel coords
  const toPixel = (pt: [number, number]): [number, number] => [pt[0] * width, pt[1] * height];
  const toNorm = (px: number, py: number): [number, number] => [
    Math.max(0, Math.min(1, px / width)),
    Math.max(0, Math.min(1, py / height)),
  ];

  const getSvgCoords = useCallback((e: React.MouseEvent | MouseEvent): [number, number] => {
    const svg = svgRef.current;
    if (!svg) return [0, 0];
    const rect = svg.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  }, []);

  // Drag handling
  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: MouseEvent) => {
      const [px, py] = getSvgCoords(e);
      const norm = toNorm(px, py);
      const newZones = zones.map((z, zi) => {
        if (zi !== dragging.zoneIdx) return z;
        const pts = [...z.points.map(p => [...p] as [number, number])];
        pts[dragging.pointIdx] = norm;
        return { ...z, points: pts };
      });
      onUpdate(newZones);
    };
    const onUp = () => setDragging(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragging, zones, width, height]);

  // Ctrl+click on polygon edge → add point
  const handlePolygonClick = (e: React.MouseEvent, zoneIdx: number) => {
    if (!interactive || !e.ctrlKey) return;
    e.preventDefault();
    e.stopPropagation();
    const [px, py] = getSvgCoords(e);
    const zone = zones[zoneIdx];
    const pts = zone.points;
    // Find nearest edge and insert after the first vertex of that edge
    let bestIdx = 0;
    let bestDist = Infinity;
    for (let i = 0; i < pts.length; i++) {
      const j = (i + 1) % pts.length;
      const [ax, ay] = toPixel(pts[i]);
      const [bx, by] = toPixel(pts[j]);
      const dist = distToSegment(px, py, ax, ay, bx, by);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = j;
      }
    }
    const norm = toNorm(px, py);
    const newPts = [...zone.points];
    newPts.splice(bestIdx, 0, norm);
    const newZones = zones.map((z, i) => (i === zoneIdx ? { ...z, points: newPts } : z));
    onUpdate(newZones);
  };

  // Ctrl+right-click on point → remove
  const handlePointContextMenu = (e: React.MouseEvent, zoneIdx: number, pointIdx: number) => {
    if (!interactive) return;
    e.preventDefault();
    e.stopPropagation();
    const zone = zones[zoneIdx];
    if (zone.points.length <= 3) return; // minimum 3 points
    const newPts = zone.points.filter((_, i) => i !== pointIdx);
    const newZones = zones.map((z, i) => (i === zoneIdx ? { ...z, points: newPts } : z));
    onUpdate(newZones);
  };

  if (!width || !height) return null;

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        pointerEvents: interactive ? 'auto' : 'none',
        userSelect: 'none',
      }}
    >
      <defs>
        {zones.map(zone => {
          const state = zoneStates.find(s => s.zone_id === zone.id);
          const active = state?.active ?? false;
          return (
            <linearGradient key={zone.id} id={`zg-${zone.id}`}>
              <stop offset="0%" stopColor={active ? '#198754' : '#fd7e14'} />
            </linearGradient>
          );
        })}
      </defs>

      {zones.map((zone, zi) => {
        if (!zone.enabled) return null;
        const state = zoneStates.find(s => s.zone_id === zone.id);
        const active = state?.active ?? false;
        const color = active ? '#198754' : '#fd7e14';
        const pts = zone.points.map(toPixel);
        const polyStr = pts.map(([x, y]) => `${x},${y}`).join(' ');

        // Centroid for label
        const cx = pts.reduce((s, [x]) => s + x, 0) / pts.length;
        const cy = pts.reduce((s, [, y]) => s + y, 0) / pts.length;

        return (
          <g key={zone.id}>
            {/* Polygon fill */}
            <polygon
              points={polyStr}
              fill={color}
              fillOpacity={0.15}
              stroke={color}
              strokeWidth={2}
              strokeOpacity={0.7}
              style={{ cursor: interactive ? 'crosshair' : 'default' }}
              onClick={e => handlePolygonClick(e, zi)}
            />

            {/* Zone label */}
            <text
              x={cx}
              y={cy}
              fill="white"
              fontSize={12}
              fontWeight="bold"
              textAnchor="middle"
              dominantBaseline="central"
              style={{ pointerEvents: 'none', textShadow: '1px 1px 2px rgba(0,0,0,0.8)' }}
            >
              {zone.name}
            </text>

            {/* Draggable points (only when interactive) */}
            {interactive &&
              pts.map(([x, y], pi) => {
                const isHovered =
                  hovered?.zoneIdx === zi && hovered?.pointIdx === pi;
                return (
                  <circle
                    key={pi}
                    cx={x}
                    cy={y}
                    r={isHovered ? 7 : 5}
                    fill="white"
                    stroke={color}
                    strokeWidth={2}
                    style={{ cursor: 'grab' }}
                    onMouseDown={e => {
                      e.preventDefault();
                      e.stopPropagation();
                      setDragging({ zoneIdx: zi, pointIdx: pi });
                    }}
                    onMouseEnter={() => setHovered({ zoneIdx: zi, pointIdx: pi })}
                    onMouseLeave={() => setHovered(null)}
                    onContextMenu={e => handlePointContextMenu(e, zi, pi)}
                  />
                );
              })}
          </g>
        );
      })}
    </svg>
  );
}

/** Distance from point (px,py) to line segment (ax,ay)-(bx,by) */
function distToSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return Math.hypot(px - ax, py - ay);
  let t = ((px - ax) * dx + (py - ay) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}
