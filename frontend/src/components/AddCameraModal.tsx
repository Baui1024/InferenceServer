import { useState } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import { useCameras } from '../context/CameraContext';

interface Props {
  show: boolean;
  onHide: () => void;
}

export default function AddCameraModal({ show, onHide }: Props) {
  const { send } = useCameras();
  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [host, setHost] = useState('');
  const [port, setPort] = useState(8081);
  const [cameraWsPort, setCameraWsPort] = useState(8082);
  const [backend, setBackend] = useState<'yolo' | 'openvino'>('yolo');
  const [confidence, setConfidence] = useState(0.5);

  const reset = () => {
    setStep(0);
    setName('');
    setHost('');
    setPort(8081);
    setCameraWsPort(8082);
    setBackend('yolo');
    setConfidence(0.5);
  };

  const handleClose = () => { reset(); onHide(); };

  const handleSubmit = () => {
    send('add_camera', {
      name: name || 'RPi Camera',
      type: 'rpi',
      host,
      port,
      detector_backend: backend,
      yolo_confidence: confidence,
      openvino_confidence: confidence,
      camera_ws_port: cameraWsPort,
    });
    handleClose();
  };

  const canSubmit = host.trim().length > 0 && port > 0 && port <= 65535;

  return (
    <Modal show={show} onHide={handleClose} centered>
      <Modal.Header closeButton className="bg-dark text-light border-secondary">
        <Modal.Title>
          {step === 0 && 'Connection Details'}
          {step === 1 && 'Detection Settings'}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body className="bg-dark text-light">

        {/* Step 0: Connection */}
        {step === 0 && (
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Camera Name</Form.Label>
              <Form.Control
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Raspberry Pi Camera"
              />
            </Form.Group>
            <Row>
              <Col xs={8}>
                <Form.Group className="mb-3">
                  <Form.Label>Host / IP</Form.Label>
                  <Form.Control
                    value={host}
                    onChange={e => setHost(e.target.value)}
                    placeholder="192.168.178.30"
                    required
                  />
                </Form.Group>
              </Col>
              <Col xs={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Port</Form.Label>
                  <Form.Control
                    type="number"
                    value={port}
                    onChange={e => setPort(Number(e.target.value))}
                    min={1} max={65535}
                  />
                </Form.Group>
              </Col>
            </Row>
            <Form.Group className="mb-3">
              <Form.Label>Camera WS Port</Form.Label>
              <Form.Control
                type="number"
                value={cameraWsPort}
                onChange={e => setCameraWsPort(Number(e.target.value))}
                min={1} max={65535}
              />
              <Form.Text className="text-muted">Port for camera hardware settings (exposure, IR, etc.)</Form.Text>
            </Form.Group>
          </Form>
        )}

        {/* Step 1: Detection */}
        {step === 1 && (
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Detector Backend</Form.Label>
              <Form.Select value={backend} onChange={e => setBackend(e.target.value as 'yolo' | 'openvino')}>
                <option value="yolo">YOLO (NVIDIA CUDA)</option>
                <option value="openvino">OpenVINO (Intel CPU/iGPU)</option>
              </Form.Select>
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Confidence Threshold: <span className="font-monospace text-success">{confidence.toFixed(2)}</span></Form.Label>
              <Form.Range
                value={confidence}
                onChange={e => setConfidence(Number(e.target.value))}
                min={0.1} max={1.0} step={0.05}
              />
            </Form.Group>
          </Form>
        )}

      </Modal.Body>
      <Modal.Footer className="bg-dark border-secondary">
        {step > 0 && <Button variant="outline-light" onClick={() => setStep(s => s - 1)}>Back</Button>}
        <div className="flex-grow-1" />
        {step < 1 ? (
          <Button variant="success" onClick={() => setStep(s => s + 1)}>Next</Button>
        ) : (
          <Button variant="success" disabled={!canSubmit} onClick={handleSubmit}>Add Camera</Button>
        )}
      </Modal.Footer>
    </Modal>
  );
}
