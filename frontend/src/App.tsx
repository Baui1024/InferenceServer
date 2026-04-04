import { useState } from 'react';
import { Navbar, Container } from 'react-bootstrap';
import { BsCameraReels } from 'react-icons/bs';
import { CameraProvider, useCameras } from './context/CameraContext';
import ConnectionStatus from './components/ConnectionStatus';
import Sidebar from './components/Sidebar';
import CameraGrid from './components/CameraGrid';
import CameraView from './components/CameraView';
import AddCameraModal from './components/AddCameraModal';
import RecordingsPanel from './components/RecordingsPanel';

type View = 'cameras' | 'recordings';

function AppContent() {
  const { selectedId } = useCameras();
  const [showAdd, setShowAdd] = useState(false);
  const [view, setView] = useState<View>('cameras');

  const mainContent = () => {
    if (selectedId) return <CameraView />;
    if (view === 'recordings') return <RecordingsPanel />;
    return <CameraGrid />;
  };

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
        <Sidebar
          onAddClick={() => setShowAdd(true)}
          view={view}
          onViewChange={setView}
        />
        <div className="flex-grow-1 overflow-hidden">
          {mainContent()}
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
