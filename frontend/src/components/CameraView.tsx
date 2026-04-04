import { Tab, Tabs, Badge, Button } from 'react-bootstrap';
import { BsArrowLeft, BsTrash, BsRecordCircle, BsStopCircle } from 'react-icons/bs';
import { useCameras } from '../context/CameraContext';
import CameraSettings from './CameraSettings';
import CameraHWSettingsPanel from './CameraHWSettings';

export default function CameraView() {
  const { cameras, selectedId, selectCamera, send, serverConfig } = useCameras();
  const camera = cameras.find(c => c.id === selectedId);

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

        {/* MJPEG stream */}
        <div className="flex-grow-1 d-flex align-items-center justify-content-center" style={{ overflow: 'hidden' }}>
          {camera.stats?.status === 'running' ? (
            <img
              src={`/stream/${camera.id}`}
              alt={camera.name}
              style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
            />
          ) : (
            <span className="text-muted">
              {camera.stats?.status === 'error' ? 'Connection error' : 'Waiting for stream...'}
            </span>
          )}
        </div>
      </div>

      {/* Settings panel */}
      <div
        className="bg-dark border-start border-secondary overflow-auto"
        style={{ width: 340, flexShrink: 0 }}
      >
        <Tabs defaultActiveKey="detection" className="px-2 pt-2" data-bs-theme="dark">
          <Tab eventKey="detection" title="Detection">
            <CameraSettings camera={camera} />
          </Tab>
          <Tab eventKey="camera" title="Camera" disabled={camera.type !== 'rpi'}>
            <CameraHWSettingsPanel camera={camera} />
          </Tab>
        </Tabs>
      </div>
    </div>
  );
}
