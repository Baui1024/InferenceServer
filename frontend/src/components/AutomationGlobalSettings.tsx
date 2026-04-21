import { useState, useEffect } from 'react';
import { Form, Button, Badge, Card } from 'react-bootstrap';
import { useCameras } from '../context/CameraContext';

export default function AutomationGlobalSettings() {
  const { automationSettings, send } = useCameras();

  const [ip, setIp] = useState(automationSettings.knx_gateway_ip);
  const [port, setPort] = useState(String(automationSettings.knx_gateway_port));
  const [connType, setConnType] = useState(automationSettings.knx_connection_type);
  const [enabled, setEnabled] = useState(automationSettings.knx_enabled);

  // Sync from server
  useEffect(() => {
    setIp(automationSettings.knx_gateway_ip);
    setPort(String(automationSettings.knx_gateway_port));
    setConnType(automationSettings.knx_connection_type);
    setEnabled(automationSettings.knx_enabled);
  }, [automationSettings]);

  const knxStatus = automationSettings.knx?.status ?? 'disconnected';
  const knxError = automationSettings.knx?.error;
  const knxAvailable = automationSettings.knx?.available ?? false;

  const statusBadge = () => {
    switch (knxStatus) {
      case 'connected': return <Badge bg="success">Connected</Badge>;
      case 'connecting': return <Badge bg="warning">Connecting...</Badge>;
      case 'error': return <Badge bg="danger">Error</Badge>;
      default: return <Badge bg="secondary">Disconnected</Badge>;
    }
  };

  const handleSave = () => {
    send('update_automation_settings', {
      knx_gateway_ip: ip,
      knx_gateway_port: parseInt(port, 10) || 3671,
      knx_connection_type: connType,
      knx_enabled: enabled,
    });
  };

  return (
    <div className="p-4" style={{ maxWidth: 600 }}>
      <h4 className="mb-4">Automation Settings</h4>

      <Card className="bg-dark text-light border-secondary mb-3">
        <Card.Header className="d-flex align-items-center justify-content-between">
          <span className="fw-bold">KNX/IP Connection</span>
          {statusBadge()}
        </Card.Header>
        <Card.Body>
          {!knxAvailable && (
            <div className="alert alert-warning py-2 small">
              <strong>xknx</strong> library not installed. KNX support is unavailable.
            </div>
          )}

          <Form.Group className="mb-3">
            <Form.Check
              type="switch"
              label="Enable KNX"
              checked={enabled}
              onChange={e => setEnabled(e.target.checked)}
            />
          </Form.Group>

          <Form.Group className="mb-3">
            <Form.Label className="small text-muted">Connection Type</Form.Label>
            <Form.Select
              size="sm"
              className="bg-dark text-light border-secondary"
              value={connType}
              onChange={e => setConnType(e.target.value as 'tunneling' | 'routing')}
              disabled={!enabled}
            >
              <option value="tunneling">Tunneling (unicast to gateway)</option>
              <option value="routing">Routing (multicast)</option>
            </Form.Select>
          </Form.Group>

          <Form.Group className="mb-3">
            <Form.Label className="small text-muted">
              {connType === 'tunneling' ? 'Gateway IP Address' : 'Local IP Address'}
            </Form.Label>
            <Form.Control
              size="sm"
              className="bg-dark text-light border-secondary"
              value={ip}
              onChange={e => setIp(e.target.value)}
              placeholder="192.168.178.5"
              disabled={!enabled}
            />
          </Form.Group>

          {connType === 'tunneling' && (
            <Form.Group className="mb-3">
              <Form.Label className="small text-muted">Gateway Port</Form.Label>
              <Form.Control
                size="sm"
                type="number"
                className="bg-dark text-light border-secondary"
                value={port}
                onChange={e => setPort(e.target.value)}
                placeholder="3671"
                disabled={!enabled}
              />
            </Form.Group>
          )}

          {knxError && (
            <div className="alert alert-danger py-2 small mb-3">
              {knxError}
            </div>
          )}

          <Button variant="primary" size="sm" onClick={handleSave}>
            Save &amp; {enabled ? 'Connect' : 'Disconnect'}
          </Button>
        </Card.Body>
      </Card>
    </div>
  );
}
