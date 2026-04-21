import { useCallback, useRef, useState, useEffect } from 'react';
import { Accordion, Form, Button, Badge, ListGroup } from 'react-bootstrap';
import { BsPlusLg, BsTrash, BsCircleFill } from 'react-icons/bs';
import { useCameras } from '../context/CameraContext';
import type { Camera, ZoneConfig, TriggerConfig } from '../types/camera';

function newZoneId(): string {
  return Math.random().toString(36).substring(2, 10);
}

function newTriggerId(): string {
  return Math.random().toString(36).substring(2, 10);
}

function defaultZone(): ZoneConfig {
  return {
    id: newZoneId(),
    name: `Zone ${Date.now() % 1000}`,
    points: [
      [0.3, 0.3],
      [0.7, 0.3],
      [0.7, 0.7],
      [0.3, 0.7],
    ],
    mode: 'intersect',
    attack_frames: 3,
    hold_time_s: 5,
    triggers: [],
    enabled: true,
  };
}

function defaultTrigger(type: 'knx' | 'webhook'): TriggerConfig {
  if (type === 'knx') {
    return {
      id: newTriggerId(),
      type: 'knx',
      group_address: '0/0/1',
      dpt: 'boolean',
      on_value: 1,
      off_value: 0,
    };
  }
  return {
    id: newTriggerId(),
    type: 'webhook',
    on_url: '',
    off_url: '',
  };
}

interface Props {
  camera: Camera;
}

export default function AutomationPanel({ camera }: Props) {
  const { send } = useCameras();
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const zoneStates = camera.stats?.zone_states ?? [];

  // Local zones state for instant UI, synced from server
  const [localZones, setLocalZones] = useState<ZoneConfig[]>(camera.zones ?? []);
  const dirtyRef = useRef(false);

  // Sync from server only when we're not mid-edit
  useEffect(() => {
    if (!dirtyRef.current) {
      setLocalZones(camera.zones ?? []);
    }
  }, [camera.zones]);

  const pushToServer = useCallback(
    (newZones: ZoneConfig[]) => {
      dirtyRef.current = true;
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        send('update_camera', { id: camera.id, zones: newZones });
        // Allow server sync again after a short grace period
        setTimeout(() => { dirtyRef.current = false; }, 500);
      }, 300);
    },
    [camera.id, send],
  );

  const updateZones = useCallback(
    (newZones: ZoneConfig[]) => {
      setLocalZones(newZones);
      pushToServer(newZones);
    },
    [pushToServer],
  );

  const addZone = () => {
    if (localZones.length >= 10) return;
    updateZones([...localZones, defaultZone()]);
  };

  const removeZone = (zoneId: string) => {
    updateZones(localZones.filter(z => z.id !== zoneId));
  };

  const updateZone = (zoneId: string, patch: Partial<ZoneConfig>) => {
    updateZones(localZones.map(z => (z.id === zoneId ? { ...z, ...patch } : z)));
  };

  const addTrigger = (zoneId: string, type: 'knx' | 'webhook') => {
    const zone = localZones.find(z => z.id === zoneId);
    if (!zone) return;
    updateZone(zoneId, { triggers: [...zone.triggers, defaultTrigger(type)] });
  };

  const removeTrigger = (zoneId: string, triggerId: string) => {
    const zone = localZones.find(z => z.id === zoneId);
    if (!zone) return;
    updateZone(zoneId, { triggers: zone.triggers.filter(t => t.id !== triggerId) });
  };

  const updateTrigger = (zoneId: string, triggerId: string, patch: Partial<TriggerConfig>) => {
    const zone = localZones.find(z => z.id === zoneId);
    if (!zone) return;
    updateZone(zoneId, {
      triggers: zone.triggers.map(t => (t.id === triggerId ? { ...t, ...patch } : t)),
    });
  };

  const zones = localZones;

  return (
    <div className="p-2">
      <div className="d-flex align-items-center justify-content-between mb-2">
        <span className="small text-muted">{zones.length}/10 zones</span>
        <Button size="sm" variant="outline-success" onClick={addZone} disabled={zones.length >= 10}>
          <BsPlusLg className="me-1" /> Add Zone
        </Button>
      </div>

      {zones.length === 0 && (
        <div className="text-muted small text-center py-3">
          No zones configured. Add a zone to start automation.
        </div>
      )}

      <Accordion flush>
        {zones.map((zone, idx) => {
          const state = zoneStates.find(s => s.zone_id === zone.id);
          const isActive = state?.active ?? false;

          return (
            <Accordion.Item
              key={zone.id}
              eventKey={String(idx)}
              className="bg-dark text-light border-secondary"
            >
              <Accordion.Header>
                <div className="d-flex align-items-center gap-2 w-100 me-2">
                  <BsCircleFill
                    size={8}
                    color={isActive ? '#198754' : (zone.enabled ? '#fd7e14' : '#6c757d')}
                    title={isActive ? 'Triggered' : (zone.enabled ? 'Idle' : 'Disabled')}
                  />
                  <span className="flex-grow-1 text-truncate">{zone.name}</span>
                  <Badge bg="secondary" className="font-monospace" style={{ fontSize: '0.65rem' }}>
                    {zone.mode}
                  </Badge>
                </div>
              </Accordion.Header>
              <Accordion.Body className="px-2 py-2">
                {/* Zone settings */}
                <Form.Group className="mb-2">
                  <Form.Label className="small text-muted mb-0">Name</Form.Label>
                  <Form.Control
                    size="sm"
                    className="bg-dark text-light border-secondary"
                    value={zone.name}
                    onChange={e => updateZone(zone.id, { name: e.target.value })}
                  />
                </Form.Group>

                <div className="d-flex gap-2 mb-2">
                  <Form.Group className="flex-grow-1">
                    <Form.Label className="small text-muted mb-0">Mode</Form.Label>
                    <Form.Select
                      size="sm"
                      className="bg-dark text-light border-secondary"
                      value={zone.mode}
                      onChange={e => updateZone(zone.id, { mode: e.target.value as 'intersect' | 'included' })}
                    >
                      <option value="intersect">Intersect</option>
                      <option value="included">Fully Included</option>
                    </Form.Select>
                  </Form.Group>
                  <Form.Group>
                    <Form.Label className="small text-muted mb-0">Enabled</Form.Label>
                    <div>
                      <Form.Check
                        type="switch"
                        checked={zone.enabled}
                        onChange={e => updateZone(zone.id, { enabled: e.target.checked })}
                      />
                    </div>
                  </Form.Group>
                </div>

                <Form.Group className="mb-2">
                  <Form.Label className="small text-muted mb-0">
                    Attack (frames/s to trigger): {zone.attack_frames}
                  </Form.Label>
                  <Form.Range
                    value={zone.attack_frames}
                    min={1}
                    max={30}
                    onChange={e => updateZone(zone.id, { attack_frames: Number(e.target.value) })}
                  />
                </Form.Group>

                <Form.Group className="mb-2">
                  <Form.Label className="small text-muted mb-0">
                    Hold time (seconds): {zone.hold_time_s}
                  </Form.Label>
                  <Form.Range
                    value={zone.hold_time_s}
                    min={1}
                    max={60}
                    step={1}
                    onChange={e => updateZone(zone.id, { hold_time_s: Number(e.target.value) })}
                  />
                </Form.Group>

                {/* Triggers */}
                <div className="border-top border-secondary pt-2 mt-2">
                  <div className="d-flex align-items-center justify-content-between mb-1">
                    <span className="small fw-bold">Triggers</span>
                    <div className="d-flex gap-1">
                      <Button
                        size="sm"
                        variant="outline-info"
                        style={{ fontSize: '0.7rem', padding: '1px 6px' }}
                        onClick={() => addTrigger(zone.id, 'knx')}
                      >
                        + KNX
                      </Button>
                      <Button
                        size="sm"
                        variant="outline-info"
                        style={{ fontSize: '0.7rem', padding: '1px 6px' }}
                        onClick={() => addTrigger(zone.id, 'webhook')}
                      >
                        + Webhook
                      </Button>
                    </div>
                  </div>

                  {zone.triggers.length === 0 && (
                    <div className="text-muted small text-center py-1">No triggers</div>
                  )}

                  <ListGroup variant="flush">
                    {zone.triggers.map(trigger => (
                      <ListGroup.Item
                        key={trigger.id}
                        className="bg-dark text-light border-secondary px-1 py-1"
                      >
                        <div className="d-flex align-items-center gap-1 mb-1">
                          <Badge bg={trigger.type === 'knx' ? 'success' : 'primary'} style={{ fontSize: '0.65rem' }}>
                            {trigger.type.toUpperCase()}
                          </Badge>
                          <div className="flex-grow-1" />
                          <Button
                            size="sm"
                            variant="outline-danger"
                            style={{ fontSize: '0.6rem', padding: '0 4px' }}
                            onClick={() => removeTrigger(zone.id, trigger.id)}
                          >
                            <BsTrash />
                          </Button>
                        </div>

                        {trigger.type === 'knx' && (
                          <>
                            <Form.Group className="mb-1">
                              <Form.Label className="small text-muted mb-0" style={{ fontSize: '0.7rem' }}>
                                Group Address
                              </Form.Label>
                              <Form.Control
                                size="sm"
                                className="bg-dark text-light border-secondary"
                                style={{ fontSize: '0.8rem' }}
                                value={trigger.group_address ?? ''}
                                placeholder="1/2/3"
                                onChange={e => updateTrigger(zone.id, trigger.id, { group_address: e.target.value })}
                              />
                            </Form.Group>
                            <div className="d-flex gap-1 mb-1">
                              <Form.Group className="flex-grow-1">
                                <Form.Label className="small text-muted mb-0" style={{ fontSize: '0.7rem' }}>DPT</Form.Label>
                                <Form.Select
                                  size="sm"
                                  className="bg-dark text-light border-secondary"
                                  style={{ fontSize: '0.8rem' }}
                                  value={trigger.dpt ?? 'boolean'}
                                  onChange={e => updateTrigger(zone.id, trigger.id, { dpt: e.target.value as 'boolean' | '1byte' })}
                                >
                                  <option value="boolean">Boolean (1.001)</option>
                                  <option value="1byte">1-Byte (5.010)</option>
                                </Form.Select>
                              </Form.Group>
                              <Form.Group>
                                <Form.Label className="small text-muted mb-0" style={{ fontSize: '0.7rem' }}>ON</Form.Label>
                                <Form.Control
                                  size="sm"
                                  type="number"
                                  className="bg-dark text-light border-secondary"
                                  style={{ width: 50, fontSize: '0.8rem' }}
                                  value={trigger.on_value ?? 1}
                                  min={0}
                                  max={255}
                                  onChange={e => updateTrigger(zone.id, trigger.id, { on_value: Number(e.target.value) })}
                                />
                              </Form.Group>
                              <Form.Group>
                                <Form.Label className="small text-muted mb-0" style={{ fontSize: '0.7rem' }}>OFF</Form.Label>
                                <Form.Control
                                  size="sm"
                                  type="number"
                                  className="bg-dark text-light border-secondary"
                                  style={{ width: 50, fontSize: '0.8rem' }}
                                  value={trigger.off_value ?? 0}
                                  min={0}
                                  max={255}
                                  onChange={e => updateTrigger(zone.id, trigger.id, { off_value: Number(e.target.value) })}
                                />
                              </Form.Group>
                            </div>
                          </>
                        )}

                        {trigger.type === 'webhook' && (
                          <>
                            <Form.Group className="mb-1">
                              <Form.Label className="small text-muted mb-0" style={{ fontSize: '0.7rem' }}>
                                ON URL (GET)
                              </Form.Label>
                              <Form.Control
                                size="sm"
                                className="bg-dark text-light border-secondary"
                                style={{ fontSize: '0.8rem' }}
                                value={trigger.on_url ?? trigger.url ?? ''}
                                placeholder="http://..."
                                onChange={e => updateTrigger(zone.id, trigger.id, { on_url: e.target.value })}
                              />
                            </Form.Group>
                            <Form.Group className="mb-1">
                              <Form.Label className="small text-muted mb-0" style={{ fontSize: '0.7rem' }}>
                                OFF URL (GET)
                              </Form.Label>
                              <Form.Control
                                size="sm"
                                className="bg-dark text-light border-secondary"
                                style={{ fontSize: '0.8rem' }}
                                value={trigger.off_url ?? ''}
                                placeholder="http://... (optional)"
                                onChange={e => updateTrigger(zone.id, trigger.id, { off_url: e.target.value })}
                              />
                            </Form.Group>
                          </>
                        )}
                      </ListGroup.Item>
                    ))}
                  </ListGroup>
                </div>

                <div className="text-end mt-2">
                  <Button
                    size="sm"
                    variant="outline-danger"
                    style={{ fontSize: '0.7rem' }}
                    onClick={() => removeZone(zone.id)}
                  >
                    <BsTrash className="me-1" /> Delete Zone
                  </Button>
                </div>
              </Accordion.Body>
            </Accordion.Item>
          );
        })}
      </Accordion>
    </div>
  );
}
