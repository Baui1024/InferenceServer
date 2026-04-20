import { useRef, useCallback } from 'react';
import { Form, Accordion } from 'react-bootstrap';
import { useCameras } from '../context/CameraContext';
import type { Camera } from '../types/camera';

interface Props {
  camera: Camera;
}

const PT_MODELS = [
  { value: 'yolo11m.pt', label: 'YOLO11 Medium' },
  { value: 'yolo11l.pt', label: 'YOLO11 Large' },
  { value: 'yolo11x.pt', label: 'YOLO11 XL' },
  { value: 'yolo26m.pt', label: 'YOLO26 Medium' },
  { value: 'yolo26l.pt', label: 'YOLO26 Large' },
  { value: 'yolo26x.pt', label: 'YOLO26 XL' },
];

export default function CameraSettings({ camera }: Props) {
  const { send, engines } = useCameras();
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const update = useCallback(
    (field: string, value: unknown) => {
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        send('update_camera', { id: camera.id, [field]: value });
      }, 300);
    },
    [camera.id, send]
  );

  return (
    <Accordion defaultActiveKey={['0']} alwaysOpen flush>
      {/* Detection */}
      <Accordion.Item eventKey="0" className="bg-dark text-light border-secondary">
        <Accordion.Header>Detection</Accordion.Header>
        <Accordion.Body>
          <Form.Group className="mb-3">
            <Form.Label>Backend</Form.Label>
            <Form.Select
              value={camera.detector_backend}
              onChange={e => update('detector_backend', e.target.value)}
            >
              <option value="yolo">YOLO (NVIDIA CUDA)</option>
              <option value="openvino">OpenVINO (Intel CPU/iGPU)</option>
            </Form.Select>
          </Form.Group>

          {camera.detector_backend === 'yolo' ? (
            <>
              <Form.Group className="mb-3">
                <Form.Label>Model</Form.Label>
                <Form.Select
                  value={camera.yolo_model}
                  onChange={e => update('yolo_model', e.target.value)}
                >
                  <optgroup label="PyTorch">
                    {PT_MODELS.map(m => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </optgroup>
                  {engines.length > 0 && (
                    <optgroup label="TensorRT (FP16)">
                      {engines.map(e => (
                        <option key={e.filename} value={e.filename}>
                          {e.source_model.replace('.pt', '')} ⚡ ({e.size_mb} MB)
                        </option>
                      ))}
                    </optgroup>
                  )}
                </Form.Select>
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>
                  Confidence: <span className="font-monospace text-success">{camera.yolo_confidence.toFixed(2)}</span>
                </Form.Label>
                <Form.Range
                  value={camera.yolo_confidence}
                  onChange={e => update('yolo_confidence', Number(e.target.value))}
                  min={0.1} max={1.0} step={0.05}
                />
              </Form.Group>
              <Form.Check
                type="switch"
                label="Show below Confidence"
                className="mb-3"
                checked={camera.show_below_confidence}
                onChange={e => update('show_below_confidence', e.target.checked)}
              />
              <Form.Check
                type="switch"
                label="Person Only"
                checked={camera.yolo_person_only}
                onChange={e => update('yolo_person_only', e.target.checked)}
              />
            </>
          ) : (
            <>
              <Form.Group className="mb-3">
                <Form.Label>Model</Form.Label>
                <Form.Select
                  value={camera.openvino_model}
                  onChange={e => update('openvino_model', e.target.value)}
                >
                  <option value="person-detection-retail-0013">person-detection-retail-0013</option>
                  <option value="person-detection-0200">person-detection-0200</option>
                  <option value="person-detection-0201">person-detection-0201</option>
                  <option value="person-detection-0202">person-detection-0202</option>
                  <option value="person-detection-0203">person-detection-0203</option>
                  <option value="pedestrian-detection-adas-0002">pedestrian-detection-adas-0002</option>
                </Form.Select>
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>
                  Confidence: <span className="font-monospace text-success">{camera.openvino_confidence.toFixed(2)}</span>
                </Form.Label>
                <Form.Range
                  value={camera.openvino_confidence}
                  onChange={e => update('openvino_confidence', Number(e.target.value))}
                  min={0.05} max={1.0} step={0.05}
                />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Device</Form.Label>
                <Form.Select
                  value={camera.openvino_device}
                  onChange={e => update('openvino_device', e.target.value)}
                >
                  <option value="CPU">CPU</option>
                  <option value="GPU">GPU</option>
                  <option value="AUTO">AUTO</option>
                </Form.Select>
              </Form.Group>
            </>
          )}
        </Accordion.Body>
      </Accordion.Item>

      {/* Pipeline */}
      <Accordion.Item eventKey="1" className="bg-dark text-light border-secondary">
        <Accordion.Header>Pipeline</Accordion.Header>
        <Accordion.Body>
          <Form.Group className="mb-3">
            <Form.Label>
              Max FPS: <span className="font-monospace text-success">{camera.max_fps}</span>
            </Form.Label>
            <Form.Range
              value={camera.max_fps}
              onChange={e => update('max_fps', Number(e.target.value))}
              min={1} max={60} step={1}
            />
          </Form.Group>
          <Form.Check
            type="switch"
            label="Motion Detection"
            checked={camera.motion_detection_enabled}
            onChange={e => update('motion_detection_enabled', e.target.checked)}
            className="mb-2"
          />
          <Form.Text className="text-muted d-block mb-3">
            Skips AI inference on static frames to save GPU resources.
          </Form.Text>
          {camera.motion_detection_enabled && (
            <>
              <Form.Check
                type="switch"
                label="Show Motion Debug"
                checked={camera.show_motion_debug}
                onChange={e => update('show_motion_debug', e.target.checked)}
                className="mb-3"
              />

              {/* Live motion bar */}
              {camera.stats?.motion_pct !== undefined && (
                <Form.Group className="mb-3">
                  <Form.Label className="d-flex justify-content-between">
                    <span>Live Motion</span>
                    <span className="font-monospace text-success">{camera.stats.motion_pct.toFixed(2)}%</span>
                  </Form.Label>
                  <div className="position-relative" style={{ height: 20 }}>
                    <div className="progress bg-secondary" style={{ height: '100%' }}>
                      <div
                        className={`progress-bar ${camera.stats.motion_pct >= camera.motion_min_area_percent ? 'bg-success' : 'bg-danger'}`}
                        style={{ width: `${Math.min(camera.stats.motion_pct / 5 * 100, 100)}%`, transition: 'width 0.3s' }}
                      />
                    </div>
                    {/* Min area marker */}
                    <div
                      className="position-absolute top-0 border-start border-warning"
                      style={{ left: `${Math.min(camera.motion_min_area_percent / 5 * 100, 100)}%`, height: '100%', borderWidth: '2px !important' }}
                      title={`Min Area threshold: ${camera.motion_min_area_percent}%`}
                    />
                  </div>
                  <Form.Text className="text-muted">
                    Green = motion triggers inference. Yellow line = min area threshold.
                  </Form.Text>
                </Form.Group>
              )}

              <Form.Group className="mb-3">
                <Form.Label>
                  Threshold: <span className="font-monospace text-success">{camera.motion_threshold.toFixed(1)}%</span>
                </Form.Label>
                <Form.Range
                  value={camera.motion_threshold}
                  onChange={e => update('motion_threshold', Number(e.target.value))}
                  min={0.5} max={20} step={0.5}
                />
                <Form.Text className="text-muted">
                  Pixel sensitivity. Lower = detects subtle changes (shadows, noise). Higher = only large brightness changes.
                </Form.Text>
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>
                  Min Area: <span className="font-monospace text-success">{camera.motion_min_area_percent.toFixed(2)}%</span>
                </Form.Label>
                <Form.Range
                  value={camera.motion_min_area_percent}
                  onChange={e => update('motion_min_area_percent', Number(e.target.value))}
                  min={0.01} max={5} step={0.01}
                />
                <Form.Text className="text-muted">
                  Minimum % of frame pixels that must change. Filters out small noise — increase if getting false triggers.
                </Form.Text>
              </Form.Group>
            </>
          )}
        </Accordion.Body>
      </Accordion.Item>
    </Accordion>
  );
}
