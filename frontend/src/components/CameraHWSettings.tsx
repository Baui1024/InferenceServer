import { useEffect, useRef, useCallback } from 'react';
import { Form, Accordion, Button } from 'react-bootstrap';
import { useCameras } from '../context/CameraContext';
import type { Camera } from '../types/camera';

interface Props {
  camera: Camera;
}

export default function CameraHWSettingsPanel({ camera }: Props) {
  const { send, hwSettings } = useCameras();
  const settings = hwSettings[camera.id];
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Request current settings on mount
  useEffect(() => {
    send('camera_hw_get', { id: camera.id });
  }, [camera.id, send]);

  const update = useCallback(
    (field: string, value: unknown) => {
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        send('camera_hw_set', { id: camera.id, settings: { [field]: value } });
      }, 200);
    },
    [camera.id, send]
  );

  if (camera.type !== 'rpi') {
    return (
      <div className="text-muted p-3 text-center small">
        Hardware settings are only available for Raspberry Pi cameras.
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="text-muted p-3 text-center small">
        Connecting to camera hardware...
      </div>
    );
  }

  return (
    <Accordion defaultActiveKey={['0', '1']} alwaysOpen flush>
      {/* IR Processing */}
      <Accordion.Item eventKey="0" className="bg-dark text-light border-secondary">
        <Accordion.Header>IR Processing</Accordion.Header>
        <Accordion.Body>
          <Form.Group className="mb-3">
            <Form.Label>IR Mode</Form.Label>
            <Form.Select
              value={settings.ir_mode ?? 'off'}
              onChange={e => update('ir_mode', e.target.value)}
            >
              <option value="off">Off</option>
              <option value="grayscale">Grayscale</option>
              <option value="blue_channel">Blue Channel</option>
            </Form.Select>
          </Form.Group>
          <Form.Check
            type="switch"
            label="CLAHE Enhancement"
            checked={settings.clahe_enabled ?? false}
            onChange={e => update('clahe_enabled', e.target.checked)}
          />
        </Accordion.Body>
      </Accordion.Item>

      {/* Exposure */}
      <Accordion.Item eventKey="1" className="bg-dark text-light border-secondary">
        <Accordion.Header>Exposure</Accordion.Header>
        <Accordion.Body>
          <Form.Check
            type="switch"
            label="Auto Exposure"
            checked={settings.ae_enable ?? false}
            onChange={e => update('ae_enable', e.target.checked)}
            className="mb-3"
          />
          <fieldset disabled={settings.ae_enable ?? false}>
            <Form.Group className="mb-3">
              <Form.Label>
                Exposure Time:{' '}
                <span className="font-monospace text-success">{settings.exposure_time ?? 30000} µs</span>
              </Form.Label>
              <Form.Range
                value={settings.exposure_time ?? 30000}
                onChange={e => update('exposure_time', Number(e.target.value))}
                min={1000} max={100000} step={1000}
              />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>
                Analogue Gain:{' '}
                <span className="font-monospace text-success">{(settings.analogue_gain ?? 4.0).toFixed(1)}</span>
              </Form.Label>
              <Form.Range
                value={settings.analogue_gain ?? 4.0}
                onChange={e => update('analogue_gain', Number(e.target.value))}
                min={1.0} max={16.0} step={0.5}
              />
            </Form.Group>
          </fieldset>
        </Accordion.Body>
      </Accordion.Item>

      {/* Encoding */}
      <Accordion.Item eventKey="2" className="bg-dark text-light border-secondary">
        <Accordion.Header>Encoding</Accordion.Header>
        <Accordion.Body>
          <Form.Group className="mb-3">
            <Form.Label>
              JPEG Quality:{' '}
              <span className="font-monospace text-success">{settings.jpeg_quality ?? 80}</span>
            </Form.Label>
            <Form.Range
              value={settings.jpeg_quality ?? 80}
              onChange={e => update('jpeg_quality', Number(e.target.value))}
              min={1} max={100} step={1}
            />
          </Form.Group>
          <Button
            variant="outline-danger"
            size="sm"
            onClick={() => send('camera_hw_reset', { id: camera.id })}
          >
            Reset to Defaults
          </Button>
        </Accordion.Body>
      </Accordion.Item>
    </Accordion>
  );
}
