import { Card, ProgressBar } from 'react-bootstrap';
import { useCameras } from '../context/CameraContext';

function MetricBar({ label, value, max, unit, variant }: {
  label: string; value: number; max: number; unit: string; variant: string;
}) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="mb-2">
      <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.8rem' }}>
        <span className="text-light">{label}</span>
        <span className="text-muted">{value}{unit} / {max}{unit}</span>
      </div>
      <ProgressBar now={pct} variant={variant} style={{ height: 8 }} />
    </div>
  );
}

export default function GpuMetrics() {
  const { gpuStats } = useCameras();

  if (!gpuStats) return null;

  const tempVariant = gpuStats.temp_c >= 85 ? 'danger' : gpuStats.temp_c >= 70 ? 'warning' : 'success';

  return (
    <Card bg="dark" text="light" className="border-secondary mb-4">
      <Card.Body className="py-2 px-3">
        <div className="d-flex align-items-center gap-2 mb-2">
          <strong style={{ fontSize: '0.85rem' }}>GPU Utilization</strong>
          <span className={`ms-auto text-${tempVariant}`} style={{ fontSize: '0.8rem' }}>
            {gpuStats.temp_c}°C
          </span>
        </div>

        <MetricBar
          label="GPU"
          value={gpuStats.gpu_util}
          max={100}
          unit="%"
          variant={gpuStats.gpu_util >= 90 ? 'danger' : gpuStats.gpu_util >= 60 ? 'warning' : 'info'}
        />

        <MetricBar
          label="VRAM"
          value={gpuStats.mem_used_mb}
          max={gpuStats.mem_total_mb}
          unit=" MB"
          variant={gpuStats.mem_used_mb / gpuStats.mem_total_mb >= 0.9 ? 'danger' : 'info'}
        />

        <MetricBar
          label="Power"
          value={Math.round(gpuStats.power_w)}
          max={Math.round(gpuStats.power_limit_w)}
          unit=" W"
          variant="info"
        />
      </Card.Body>
    </Card>
  );
}
