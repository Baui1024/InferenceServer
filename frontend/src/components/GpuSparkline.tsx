import { useRef, useEffect } from 'react';
import { useCameras } from '../context/CameraContext';

const MAX_POINTS = 60;
const W = 120;
const H = 28;

export default function GpuSparkline() {
  const { gpuStats } = useCameras();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const historyRef = useRef<number[]>([]);

  useEffect(() => {
    if (gpuStats === null) return;
    const h = historyRef.current;
    h.push(gpuStats.gpu_util);
    if (h.length > MAX_POINTS) h.shift();

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, W, H);

    // Draw filled area + line
    const len = h.length;
    if (len < 2) return;

    const stepX = W / (MAX_POINTS - 1);
    const offsetX = (MAX_POINTS - len) * stepX;

    ctx.beginPath();
    ctx.moveTo(offsetX, H - (h[0] / 100) * H);
    for (let i = 1; i < len; i++) {
      ctx.lineTo(offsetX + i * stepX, H - (h[i] / 100) * H);
    }
    ctx.strokeStyle = '#0dcaf0';
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Fill under the line
    ctx.lineTo(offsetX + (len - 1) * stepX, H);
    ctx.lineTo(offsetX, H);
    ctx.closePath();
    ctx.fillStyle = 'rgba(13,202,240,0.15)';
    ctx.fill();
  }, [gpuStats]);

  if (!gpuStats) return null;

  const util = gpuStats.gpu_util;

  return (
    <div className="d-flex align-items-center gap-2" style={{ fontSize: '0.75rem' }}>
      <span className="text-muted">GPU</span>
      <canvas
        ref={canvasRef}
        style={{ width: W, height: H, display: 'block' }}
      />
      <span className="text-light" style={{ minWidth: 32, textAlign: 'right' }}>
        {util}%
      </span>
    </div>
  );
}
