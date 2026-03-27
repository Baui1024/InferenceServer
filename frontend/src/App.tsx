import { useState } from 'react';
import { Navbar, Container } from 'react-bootstrap';
import { BsCameraReels } from 'react-icons/bs';
import { CameraProvider, useCameras } from './context/CameraContext';
import ConnectionStatus from './components/ConnectionStatus';
import Sidebar from './components/Sidebar';
import CameraGrid from './components/CameraGrid';
import CameraView from './components/CameraView';
import AddCameraModal from './components/AddCameraModal';

function AppContent() {
  const { selectedId } = useCameras();
  const [showAdd, setShowAdd] = useState(false);

  return (
    <div className="d-flex flex-column vh-100" data-bs-theme="dark">
      <Navbar bg="dark" variant="dark" className="border-bottom border-secondary px-3 py-1" style={{ flexShrink: 0 }}>
        <Container fluid className="px-0">
          <Navbar.Brand className="d-flex align-items-center gap-2 mb-0">
            <BsCameraReels size={20} />
            <span className="fw-bold">Inference Server</span>
            <ConnectionStatus />
          </Navbar.Brand>
        </Container>
      </Navbar>

      <div className="d-flex flex-grow-1 overflow-hidden">
        <Sidebar onAddClick={() => setShowAdd(true)} />
        <div className="flex-grow-1 overflow-hidden">
          {selectedId ? <CameraView /> : <CameraGrid />}
        </div>
      </div>

      <AddCameraModal show={showAdd} onHide={() => setShowAdd(false)} />
    </div>
  );
}

export default function App() {
  return (
    <CameraProvider>
      <AppContent />
    </CameraProvider>
  );
}
