import { useEffect, useRef, useState } from 'react';
import { Card, Col, Row, Badge } from 'react-bootstrap';
import { BsCameraVideo, BsCameraReels } from 'react-icons/bs';
import { useCameras } from '../context/CameraContext';
import type { Camera } from '../types/camera';

/** Thumbnail that polls /snapshot/ every 2s instead of opening a persistent MJPEG stream. */
function Thumbnail({ cam }: { cam: Camera }) {
  const [src, setSrc] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval>>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    const load = () => {
      if (cam.stats?.status !== 'running') return;
      fetch(`/snapshot/${cam.id}`)
        .then(r => {
          if (!r.ok || r.status === 204) return null;
          return r.blob();
        })
        .then(blob => {
          if (blob && mountedRef.current) {
            const url = URL.createObjectURL(blob);
            setSrc(prev => {
              if (prev) URL.revokeObjectURL(prev);
              return url;
            });
          }
        })
        .catch(() => {});
    };
    load();
    timerRef.current = setInterval(load, 2000);
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearInterval(timerRef.current);
      setSrc(prev => { if (prev) URL.revokeObjectURL(prev); return null; });
    };
  }, [cam.id, cam.stats?.status]);

  if (cam.stats?.status !== 'running' || !src) {
    return (
      <span className="text-muted small">
        {cam.stats?.status === 'error' ? 'Connection error' : 'Not streaming'}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={cam.name}
      style={{ width: '100%', height: '100%', objectFit: 'contain' }}
    />
  );
}

export default function CameraGrid() {
  const { cameras, selectCamera } = useCameras();

  if (cameras.length === 0) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100 text-muted">
        <div className="text-center">
          <BsCameraVideo size={48} className="mb-3 opacity-50" />
          <p>No cameras configured.</p>
          <p className="small">Click "Add Camera" to get started.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3 overflow-auto h-100">
      <Row xs={1} sm={2} lg={3} xl={4} className="g-3">
        {cameras.map(cam => (
          <Col key={cam.id}>
            <Card
              bg="dark"
              text="light"
              className="border-secondary h-100"
              style={{ cursor: 'pointer' }}
              onClick={() => selectCamera(cam.id)}
            >
              <div
                className="bg-black d-flex align-items-center justify-content-center"
                style={{ height: 180, overflow: 'hidden' }}
              >
                <Thumbnail cam={cam} />
              </div>
              <Card.Body className="py-2 px-3">
                <div className="d-flex align-items-center gap-2">
                  {cam.type === 'recording' ? <BsCameraReels /> : <BsCameraVideo />}
                  <span className="text-truncate fw-bold flex-grow-1">{cam.name}</span>
                  <Badge bg={cam.stats?.status === 'running' ? 'success' : 'secondary'} pill>
                    {cam.stats?.status ?? 'unknown'}
                  </Badge>
                </div>
                {cam.stats && (
                  <div className="small text-muted font-monospace mt-1">
                    {cam.stats.fps} fps &middot; {cam.stats.inference_ms}ms
                  </div>
                )}
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
