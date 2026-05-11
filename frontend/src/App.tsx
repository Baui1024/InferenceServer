import { useState } from 'react';
import { Navbar, Container } from 'react-bootstrap';
import { BsCameraReels } from 'react-icons/bs';
import { CameraProvider, useCameras } from './context/CameraContext';
import ConnectionStatus from './components/ConnectionStatus';
import GpuSparkline from './components/GpuSparkline';
import Sidebar from './components/Sidebar';
import CameraGrid from './components/CameraGrid';
import CameraView from './components/CameraView';
import AddCameraModal from './components/AddCameraModal';
import RecordingsPanel from './components/RecordingsPanel';
import EngineManager from './components/EngineManager';
import AutomationGlobalSettings from './components/AutomationGlobalSettings';

type View = 'cameras' | 'recordings' | 'engines' | 'settings';

function AppContent() {
  const { selectedId } = useCameras();
  const [showAdd, setShowAdd] = useState(false);
  const [view, setView] = useState<View>('cameras');

  const mainContent = () => {
    if (selectedId) return <CameraView />;
    if (view === 'recordings') return <RecordingsPanel />;
    if (view === 'engines') return <EngineManager />;
    if (view === 'settings') return <AutomationGlobalSettings />;
    return <CameraGrid />;
  };

  return (
    <div className="main-app d-flex flex-column vh-100">
      <Navbar bg="dark" variant="dark" className="navbar border-bottom border-secondary px-3 py-1" style={{ flexShrink: 0 }}>
        <Container fluid className="px-0">
          <Navbar.Brand className="navbar__brand d-flex align-items-center gap-2 mb-0">
            <BsCameraReels size={20} />
            <span className="fw-bold">Inference Server</span>
            <ConnectionStatus />
          </Navbar.Brand>
          <GpuSparkline />
        </Container>
      </Navbar>

      <div className="container-fluid app__body">
        <Sidebar
          onAddClick={() => setShowAdd(true)}
          view={view}
          onViewChange={setView}
        />
        <div className="main-content__wrapper flex-grow-1 overflow-hidden  col-12 col-sm-12 col-md-9">
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
