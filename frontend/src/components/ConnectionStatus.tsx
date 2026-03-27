import { Badge } from 'react-bootstrap';
import { useCameras } from '../context/CameraContext';
import type { WSState } from '../hooks/useWebSocket';

const variants: Record<WSState, string> = {
  connected: 'success',
  disconnected: 'danger',
  reconnecting: 'warning',
};

export default function ConnectionStatus() {
  const { wsState } = useCameras();
  return (
    <Badge bg={variants[wsState]} className="ms-2" pill>
      {wsState}
    </Badge>
  );
}
