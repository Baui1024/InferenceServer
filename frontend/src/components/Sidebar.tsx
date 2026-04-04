import { ListGroup, Button, Nav } from 'react-bootstrap';
import { BsCameraVideo, BsCpu, BsPlusLg, BsCameraReels, BsGrid } from 'react-icons/bs';
import { useCameras } from '../context/CameraContext';
import type { Camera } from '../types/camera';

function statusColor(cam: Camera): string {
  const s = cam.stats?.status;
  if (s === 'running') return '#198754';
  if (s === 'error') return '#dc3545';
  return '#6c757d';
}

interface Props {
  onAddClick: () => void;
  view: 'cameras' | 'recordings';
  onViewChange: (v: 'cameras' | 'recordings') => void;
}

export default function Sidebar({ onAddClick, view, onViewChange }: Props) {
  const { cameras, selectedId, selectCamera, serverConfig } = useCameras();

  const handleCameraClick = (id: string) => {
    selectCamera(id);
    onViewChange('cameras');
  };

  return (
    <div className="d-flex flex-column h-100 bg-dark text-light" style={{ width: 260 }}>
      {/* View toggle */}
      <Nav variant="pills" className="px-3 pt-2 gap-1" data-bs-theme="dark">
        <Nav.Item>
          <Nav.Link
            active={view === 'cameras' && !selectedId}
            onClick={() => { selectCamera(null); onViewChange('cameras'); }}
            className="py-1 px-2 d-flex align-items-center gap-1"
            style={{ fontSize: '0.8rem' }}
          >
            <BsGrid size={12} /> Cameras
          </Nav.Link>
        </Nav.Item>
        {serverConfig.recording_enabled && (
          <Nav.Item>
            <Nav.Link
              active={view === 'recordings' && !selectedId}
              onClick={() => { selectCamera(null); onViewChange('recordings'); }}
              className="py-1 px-2 d-flex align-items-center gap-1"
              style={{ fontSize: '0.8rem' }}
            >
              <BsCameraReels size={12} /> Recordings
            </Nav.Link>
          </Nav.Item>
        )}
      </Nav>

      <div className="p-3 border-bottom border-secondary d-flex align-items-center justify-content-between">
        <h6 className="mb-0">Cameras</h6>
        <Button size="sm" variant="outline-light" onClick={onAddClick}>
          <BsPlusLg />
        </Button>
      </div>

      <ListGroup variant="flush" className="flex-grow-1 overflow-auto">
        {cameras.length === 0 && (
          <div className="text-muted small p-3 text-center">
            No cameras added yet.
          </div>
        )}
        {cameras.map(cam => (
          <ListGroup.Item
            key={cam.id}
            action
            active={cam.id === selectedId}
            onClick={() => handleCameraClick(cam.id)}
            className="bg-dark text-light border-secondary d-flex align-items-center gap-2"
          >
            <span
              style={{
                width: 8, height: 8, borderRadius: '50%',
                backgroundColor: statusColor(cam), flexShrink: 0,
              }}
            />
            {cam.type === 'esp32' ? <BsCpu size={14} /> : cam.type === 'recording' ? <BsCameraReels size={14} /> : <BsCameraVideo size={14} />}
            <span className="text-truncate flex-grow-1">{cam.name}</span>
            {cam.stats?.recording && (
              <span style={{ color: '#dc3545', fontSize: 10 }} title="Recording">&#9679;</span>
            )}
            {cam.stats && (
              <small className="text-muted font-monospace">{cam.stats.fps} fps</small>
            )}
          </ListGroup.Item>
        ))}
      </ListGroup>

      <div className="p-2 border-top border-secondary">
        <Button variant="success" size="sm" className="w-100" onClick={onAddClick}>
          <BsPlusLg className="me-1" /> Add Camera
        </Button>
      </div>
    </div>
  );
}
