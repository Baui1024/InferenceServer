import { useState, useCallback, useEffect, useRef } from 'react';
import { Tab, Tabs, Badge, Button, Form, OverlayTrigger, Tooltip } from 'react-bootstrap';
import { BsArrowLeft, BsTrash, BsRecordCircle, BsStopCircle, BsPauseFill, BsPlayFill, BsSkipForwardFill, BsSkipBackwardFill, BsStopFill } from 'react-icons/bs';
import { useCameras } from '../context/CameraContext';
import CameraSettings from './CameraSettings';
import CameraHWSettingsPanel from './CameraHWSettings';
import AutomationPanel from './AutomationPanel';
import ZoneOverlay from './ZoneOverlay';

export default function CameraView() {
  const { cameras, selectedId, selectCamera, send, serverConfig } = useCameras();
  const camera = cameras.find(c => c.id === selectedId);
  const [rangeEditing, setRangeEditing] = useState(false);
  const [localStart, setLocalStart] = useState<string>('');
  const [localEnd, setLocalEnd] = useState<string>('');

  // Optimistic playback state — flips instantly on click, reconciled by backend stats
  const [optPaused, setOptPaused] = useState<boolean | null>(null);
  const [optFrame, setOptFrame] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState('detection');
  const [imgSize, setImgSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const imgContainerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Sync local range inputs when playback info changes and we're not editing
  const pb = camera?.stats?.playback;

  // Reconcile optimistic state when backend stats arrive
  useEffect(() => {
    if (pb) {
      setOptPaused(null);
      setOptFrame(null);
    }
  }, [pb?.paused, pb?.current_frame]);

  useEffect(() => {
    if (pb && !rangeEditing) {
      setLocalStart(String(pb.start_frame));
      setLocalEnd(String(pb.end_frame));
    }
  }, [pb?.start_frame, pb?.end_frame, rangeEditing]);

  // Track rendered image size for ZoneOverlay
  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;
    const update = () => setImgSize({ w: img.clientWidth, h: img.clientHeight });
    const ro = new ResizeObserver(update);
    ro.observe(img);
    img.addEventListener('load', update);
    return () => { ro.disconnect(); img.removeEventListener('load', update); };
  }, [camera?.stats?.status]);

  const commitRange = useCallback((field: 'start_frame' | 'end_frame', value: string) => {
    const num = parseInt(value, 10);
    if (!isNaN(num) && camera) {
      send('playback_set_range', { id: camera.id, [field]: num });
    }
  }, [camera?.id, send]);

  const formatTime = useCallback((frames: number, fps: number) => {
    if (!fps) return '0:00';
    const secs = Math.floor(frames / fps);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }, []);

  if (!camera) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100 text-muted">
        Camera not found.
      </div>
    );
  }

  const isRecording = camera.stats?.recording ?? false;
  const isPlayback = camera.type === 'recording';

  const handleRemove = () => {
    if (confirm(`Remove "${camera.name}"?`)) {
      send('remove_camera', { id: camera.id });
      selectCamera(null);
    }
  };

  const handleStopPlayback = async () => {
    // Stop the playback pipeline by stopping the camera
    send('remove_camera', { id: camera.id });
    selectCamera(null);
  };

  const toggleRecording = () => {
    if (isRecording) {
      send('stop_recording', { id: camera.id });
    } else {
      send('start_recording', { id: camera.id });
    }
  };

  return (
    <div className="d-flex flex-column flex-lg-row h-100">
      {/* Stream */}
      <div className="flex-grow-1 bg-black d-flex flex-column">
        {/* Header bar */}
        <div className="d-flex align-items-center gap-2 p-2 bg-dark border-bottom border-secondary">
          <Button variant="outline-light" size="sm" onClick={() => selectCamera(null)}>
            <BsArrowLeft />
          </Button>
          <span className="fw-bold">{camera.name}</span>
          <Badge bg={camera.stats?.status === 'running' ? 'success' : 'secondary'} pill>
            {camera.stats?.status ?? 'unknown'}
          </Badge>
          {camera.stats && (
            <span className="font-monospace small text-muted">
              {camera.stats.fps} fps &middot; {camera.stats.inference_ms}ms &middot; {camera.stats.detection_count} detections
            </span>
          )}
          <div className="flex-grow-1" />
          {serverConfig.recording_enabled && !isPlayback && (
            <Button
              variant={isRecording ? 'danger' : 'outline-danger'}
              size="sm"
              onClick={toggleRecording}
              title={isRecording ? 'Stop recording' : 'Start recording'}
            >
              {isRecording ? <><BsStopCircle className="me-1" /> REC</> : <BsRecordCircle />}
            </Button>
          )}
          {isPlayback ? (
            <Button variant="outline-warning" size="sm" onClick={handleStopPlayback}>
              Stop Playback
            </Button>
          ) : (
            <Button variant="outline-danger" size="sm" onClick={handleRemove}>
              <BsTrash />
            </Button>
          )}
        </div>

        {/* MJPEG stream with zone overlay */}
        <div className="flex-grow-1 d-flex align-items-center justify-content-center" style={{ overflow: 'hidden' }}>
          {camera.stats?.status === 'running' ? (
            <div ref={imgContainerRef} style={{ position: 'relative', display: 'inline-block' }}>
              <img
                ref={imgRef}
                src={`/stream/${camera.id}`}
                alt={camera.name}
                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', display: 'block' }}
              />
              {(camera.zones?.length ?? 0) > 0 && imgSize.w > 0 && (
                <ZoneOverlay
                  zones={camera.zones ?? []}
                  zoneStates={camera.stats?.zone_states ?? []}
                  onUpdate={zones => send('update_camera', { id: camera.id, zones })}
                  interactive={activeTab === 'automation'}
                  width={imgSize.w}
                  height={imgSize.h}
                />
              )}
            </div>
          ) : (
            <span className="text-muted">
              {camera.stats?.status === 'error' ? 'Connection error' : 'Waiting for stream...'}
            </span>
          )}
        </div>

        {/* Playback controls */}
        {isPlayback && camera.stats?.playback && (() => {
          const pb = camera.stats.playback;
          const fps = pb.native_fps || 15;
          const paused = optPaused ?? pb.paused;
          const frame = optFrame ?? pb.current_frame;
          return (
            <div className="bg-dark border-top border-secondary px-3 py-2">
              {/* Transport controls + timeline */}
              <div className="d-flex align-items-center gap-2 mb-1">
                <OverlayTrigger placement="top" overlay={<Tooltip>Stop (jump to start)</Tooltip>}>
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={() => {
                      setOptPaused(true);
                      setOptFrame(pb.start_frame);
                      send('playback_stop', { id: camera.id });
                    }}
                  >
                    <BsStopFill />
                  </Button>
                </OverlayTrigger>
                <OverlayTrigger placement="top" overlay={<Tooltip>Previous frame</Tooltip>}>
                  <span>
                    <Button
                      variant="outline-light"
                      size="sm"
                      disabled={!paused}
                      onClick={() => {
                        setOptFrame(Math.max(pb.start_frame, frame - 1));
                        send('playback_step_back', { id: camera.id });
                      }}
                    >
                      <BsSkipBackwardFill />
                    </Button>
                  </span>
                </OverlayTrigger>
                <Button
                  variant={paused ? 'outline-success' : 'outline-warning'}
                  size="sm"
                  onClick={() => {
                    setOptPaused(!paused);
                    send(paused ? 'playback_resume' : 'playback_pause', { id: camera.id });
                  }}
                  title={paused ? 'Play' : 'Pause'}
                >
                  {paused ? <BsPlayFill /> : <BsPauseFill />}
                </Button>
                <OverlayTrigger placement="top" overlay={<Tooltip>Next frame</Tooltip>}>
                  <span>
                    <Button
                      variant="outline-light"
                      size="sm"
                      disabled={!paused}
                      onClick={() => {
                        setOptFrame(Math.min(pb.end_frame, frame + 1));
                        send('playback_step', { id: camera.id });
                      }}
                    >
                      <BsSkipForwardFill />
                    </Button>
                  </span>
                </OverlayTrigger>

                <Form.Range
                  className="flex-grow-1"
                  value={frame}
                  min={pb.start_frame}
                  max={pb.end_frame}
                  onChange={e => {
                    const f = Number(e.target.value);
                    setOptFrame(f);
                    send('playback_seek', { id: camera.id, frame: f });
                  }}
                  title={`Frame ${frame}`}
                />

                <span className="font-monospace small text-muted text-nowrap">
                  {formatTime(frame, fps)} / {formatTime(pb.total_frames, fps)}
                </span>
                <span className="font-monospace small text-muted text-nowrap">
                  F{frame}
                </span>
              </div>

              {/* Range controls */}
              <div className="d-flex align-items-center gap-2">
                <Button
                  variant={rangeEditing ? 'outline-info' : 'outline-secondary'}
                  size="sm"
                  onClick={() => {
                    if (!rangeEditing) {
                      setLocalStart(String(pb.start_frame));
                      setLocalEnd(String(pb.end_frame));
                    }
                    setRangeEditing(!rangeEditing);
                  }}
                >
                  {rangeEditing ? 'Done' : 'Set Range'}
                </Button>
                {rangeEditing && (
                  <>
                    <span className="small text-muted">Start:</span>
                    <Form.Control
                      type="number"
                      size="sm"
                      className="bg-dark text-light border-secondary"
                      style={{ width: 80 }}
                      value={localStart}
                      min={0}
                      max={pb.end_frame - 1}
                      onChange={e => setLocalStart(e.target.value)}
                      onBlur={() => commitRange('start_frame', localStart)}
                      onKeyDown={e => { if (e.key === 'Enter') commitRange('start_frame', localStart); }}
                    />
                    <span className="small text-muted">End:</span>
                    <Form.Control
                      type="number"
                      size="sm"
                      className="bg-dark text-light border-secondary"
                      style={{ width: 80 }}
                      value={localEnd}
                      min={pb.start_frame + 1}
                      max={pb.total_frames}
                      onChange={e => setLocalEnd(e.target.value)}
                      onBlur={() => commitRange('end_frame', localEnd)}
                      onKeyDown={e => { if (e.key === 'Enter') commitRange('end_frame', localEnd); }}
                    />
                    <Button
                      variant="outline-secondary"
                      size="sm"
                      onClick={() => {
                        send('playback_set_range', { id: camera.id, start_frame: 0, end_frame: pb.total_frames });
                        setLocalStart('0');
                        setLocalEnd(String(pb.total_frames));
                      }}
                    >
                      Reset
                    </Button>
                  </>
                )}
              </div>
            </div>
          );
        })()}
      </div>

      {/* Settings panel */}
      <div
        className="bg-dark border-start border-secondary overflow-auto"
        style={{ width: 340, flexShrink: 0 }}
      >
        <Tabs activeKey={activeTab} onSelect={k => setActiveTab(k ?? 'detection')} className="px-2 pt-2">
          <Tab eventKey="detection" title="Detection">
            <CameraSettings camera={camera} />
          </Tab>
          <Tab eventKey="camera" title="Camera" disabled={camera.type !== 'rpi'}>
            <CameraHWSettingsPanel camera={camera} />
          </Tab>
          <Tab eventKey="automation" title="Automation">
            <AutomationPanel camera={camera} />
          </Tab>
        </Tabs>
      </div>
    </div>
  );
}
