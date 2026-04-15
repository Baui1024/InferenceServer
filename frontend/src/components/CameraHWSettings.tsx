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
    <Accordion defaultActiveKey={['0']} flush>
      {/* Day/Night & Exposure */}
      <Accordion.Item eventKey="0" className="bg-dark text-light border-secondary">
        <Accordion.Header>Day / Night &amp; Exposure</Accordion.Header>
        <Accordion.Body>
          <Form.Group className="mb-3">
            <Form.Label>Day/Night Mode</Form.Label>
            <Form.Select
              value={settings.daynightmode ?? '0xff'}
              onChange={e => update('daynightmode', e.target.value)}
            >
              <option value="0xff">Color (Day)</option>
              <option value="0xfe">B&W (Night/IR)</option>
              <option value="0xfc">External Trigger</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>IR-CUT Direction</Form.Label>
            <Form.Select
              value={settings.ircutdir ?? '0x00'}
              onChange={e => update('ircutdir', e.target.value)}
            >
              <option value="0x00">Normal (0)</option>
              <option value="0x01">Inverted (1)</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>IR Trigger Polarity</Form.Label>
            <Form.Select
              value={settings.irtrigger ?? '0x00'}
              onChange={e => update('irtrigger', e.target.value)}
            >
              <option value="0x00">Default</option>
              <option value="0x01">Inverted</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Shutter Speed</Form.Label>
            <Form.Select
              value={settings.mshutter ?? '0x40'}
              onChange={e => update('mshutter', e.target.value)}
            >
              <option value="0x40">Auto</option>
              <option value="0x41">1/30s (1/25s PAL)</option>
              <option value="0x42">1/60s (1/50s PAL)</option>
              <option value="0x43">1/120s (1/100s PAL)</option>
              <option value="0x44">1/240s (1/200s PAL)</option>
              <option value="0x45">1/480s (1/400s PAL)</option>
              <option value="0x46">1/1000s</option>
              <option value="0x47">1/2000s</option>
              <option value="0x48">1/5000s</option>
              <option value="0x49">1/10000s</option>
              <option value="0x4a">1/50000s</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              AGC (Gain Limit):{' '}
              <span className="font-monospace text-success">{settings.agc ?? '0x00'}</span>
            </Form.Label>
            <Form.Select
              value={settings.agc ?? '0x00'}
              onChange={e => update('agc', e.target.value)}
            >
              {Array.from({ length: 16 }, (_, i) => {
                const hex = '0x' + i.toString(16).padStart(2, '0');
                return <option key={hex} value={hex}>{hex} ({i})</option>;
              })}
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              AE Speed — AGC:{' '}
              <span className="font-monospace text-success">{settings.aespeed_agc ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.aespeed_agc ?? '0x32', 16)}
              onChange={e => update('aespeed_agc', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={100} step={1}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              AE Speed — Shutter:{' '}
              <span className="font-monospace text-success">{settings.aespeed_shutter ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.aespeed_shutter ?? '0x32', 16)}
              onChange={e => update('aespeed_shutter', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={100} step={1}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Low Light Mode</Form.Label>
            <Form.Select
              value={settings.lowlight ?? '0x00'}
              onChange={e => update('lowlight', e.target.value)}
            >
              <option value="0x00">Off (fixed frame rate)</option>
              <option value="0x01">1/2 frame rate</option>
              <option value="0x03">1/4 frame rate</option>
              <option value="0x05">1/6 frame rate</option>
              <option value="0x07">1/8 frame rate</option>
              <option value="0x09">1/10 frame rate</option>
              <option value="0x0b">1/15 frame rate</option>
              <option value="0x0d">1/20 frame rate</option>
              <option value="0x0f">1/25 frame rate</option>
              <option value="0x11">1/30 frame rate</option>
            </Form.Select>
          </Form.Group>
        </Accordion.Body>
      </Accordion.Item>

      {/* Image Processing */}
      <Accordion.Item eventKey="1" className="bg-dark text-light border-secondary">
        <Accordion.Header>Image Processing</Accordion.Header>
        <Accordion.Body>
          <Form.Group className="mb-3">
            <Form.Label>
              Brightness:{' '}
              <span className="font-monospace text-success">{settings.brightness ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.brightness ?? '0x32', 16)}
              onChange={e => update('brightness', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={100} step={1}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              Contrast:{' '}
              <span className="font-monospace text-success">{settings.contrast ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.contrast ?? '0x80', 16)}
              onChange={e => update('contrast', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={255} step={1}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              Saturation:{' '}
              <span className="font-monospace text-success">{settings.saturation ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.saturation ?? '0x32', 16)}
              onChange={e => update('saturation', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={100} step={1}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              Sharpness:{' '}
              <span className="font-monospace text-success">{settings.sharppen ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.sharppen ?? '0x05', 16)}
              onChange={e => update('sharppen', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={10} step={1}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Denoise</Form.Label>
            <Form.Select
              value={settings.denoise ?? '0x00'}
              onChange={e => update('denoise', e.target.value)}
            >
              <option value="0x00">2D Off / 3D Off</option>
              <option value="0x01">2D Off / 3D Low</option>
              <option value="0x02">2D Off / 3D Mid</option>
              <option value="0x03">2D Off / 3D High</option>
              <option value="0x04">2D Low / 3D Off</option>
              <option value="0x05">2D Low / 3D Low</option>
              <option value="0x06">2D Low / 3D Mid</option>
              <option value="0x07">2D Low / 3D High</option>
              <option value="0x08">2D Mid / 3D Off</option>
              <option value="0x09">2D Mid / 3D Low</option>
              <option value="0x0a">2D Mid / 3D Mid</option>
              <option value="0x0b">2D Mid / 3D High</option>
              <option value="0x0c">2D High / 3D Off</option>
              <option value="0x0d">2D High / 3D Low</option>
              <option value="0x0e">2D High / 3D Mid</option>
              <option value="0x0f">2D High / 3D High</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>WDR Mode</Form.Label>
            <Form.Select
              value={settings.wdrmode ?? '0x00'}
              onChange={e => update('wdrmode', e.target.value)}
            >
              <option value="0x00">Off</option>
              <option value="0x01">Low Backlight</option>
              <option value="0x02">High Backlight</option>
              <option value="0x03">DOL WDR</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              WDR Target Brightness:{' '}
              <span className="font-monospace text-success">{settings.wdrtargetbr ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.wdrtargetbr ?? '0x30', 16)}
              onChange={e => update('wdrtargetbr', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={255} step={1}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              WDR Bright Area Target:{' '}
              <span className="font-monospace text-success">{settings.wdrbtargetbr ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.wdrbtargetbr ?? '0x30', 16)}
              onChange={e => update('wdrbtargetbr', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={255} step={1}
            />
          </Form.Group>
        </Accordion.Body>
      </Accordion.Item>

      {/* White Balance */}
      <Accordion.Item eventKey="2" className="bg-dark text-light border-secondary">
        <Accordion.Header>White Balance</Accordion.Header>
        <Accordion.Body>
          <Form.Group className="mb-3">
            <Form.Label>WB Mode</Form.Label>
            <Form.Select
              value={settings.wbmode ?? '0x18'}
              onChange={e => update('wbmode', e.target.value)}
            >
              <option value="0x18">Auto</option>
              <option value="0x1b">Manual</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              AWB R-Gain (read-only):{' '}
              <span className="font-monospace text-success">{settings.awbgain_rgain ?? '—'}</span>
            </Form.Label>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              AWB B-Gain (read-only):{' '}
              <span className="font-monospace text-success">{settings.awbgain_bgain ?? '—'}</span>
            </Form.Label>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              Manual WB R-Gain:{' '}
              <span className="font-monospace text-success">{settings.mwbgain_rgain ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.mwbgain_rgain ?? '0x80', 16)}
              onChange={e => update('mwbgain_rgain', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={255} step={1}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              Manual WB B-Gain:{' '}
              <span className="font-monospace text-success">{settings.mwbgain_bgain ?? '—'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.mwbgain_bgain ?? '0x80', 16)}
              onChange={e => update('mwbgain_bgain', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={255} step={1}
            />
          </Form.Group>
        </Accordion.Body>
      </Accordion.Item>

      {/* Camera Mode & Output */}
      <Accordion.Item eventKey="3" className="bg-dark text-light border-secondary">
        <Accordion.Header>Camera Mode</Accordion.Header>
        <Accordion.Body>
          <Form.Group className="mb-3">
            <Form.Label>Video Format</Form.Label>
            <Form.Select
              value={settings.videoformat ?? '0x01'}
              onChange={e => update('videoformat', e.target.value)}
            >
              <option value="0x00">PAL (25 fps)</option>
              <option value="0x01">NTSC (30 fps)</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Mirror Mode</Form.Label>
            <Form.Select
              value={settings.mirrormode ?? '0x00'}
              onChange={e => update('mirrormode', e.target.value)}
            >
              <option value="0x00">Normal</option>
              <option value="0x01">Mirror</option>
              <option value="0x02">Flip (180°)</option>
              <option value="0x03">Mirror + Flip (180°)</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Camera Mode</Form.Label>
            <Form.Select
              value={settings.cameramode ?? '0x00'}
              onChange={e => update('cameramode', e.target.value)}
            >
              <option value="0x00">Stream</option>
              <option value="0x01">Capture</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>
              Frame Drop (nodf):{' '}
              <span className="font-monospace text-success">{settings.nodf ?? '0x00'}</span>
            </Form.Label>
            <Form.Range
              value={parseInt(settings.nodf ?? '0x00', 16)}
              onChange={e => update('nodf', '0x' + Number(e.target.value).toString(16).padStart(2, '0'))}
              min={0} max={255} step={1}
            />
            <Form.Text className="text-muted">
              Effective FPS = base FPS / (1 + nodf)
            </Form.Text>
          </Form.Group>
        </Accordion.Body>
      </Accordion.Item>

      {/* Encoding */}
      <Accordion.Item eventKey="4" className="bg-dark text-light border-secondary">
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
