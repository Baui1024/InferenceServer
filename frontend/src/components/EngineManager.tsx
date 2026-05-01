import { Card, Table, Button, ProgressBar, Badge } from 'react-bootstrap';
import { BsTrash, BsGpuCard, BsArrowRepeat } from 'react-icons/bs';
import { useCameras } from '../context/CameraContext';
import GpuMetrics from './GpuMetrics';

export default function EngineManager() {
  const { serverConfig, engines, compileProgress, send } = useCameras();
  const { gpu, compilable_models } = serverConfig;

  const compiledSet = new Set(engines.map(e => e.source_model));
  const isCompiling = compileProgress !== null;

  return (
    <div className="p-4 overflow-auto h-100">
      <h4 className="text-light mb-3">
        <BsGpuCard className="me-2" />
        TensorRT Engine Manager
      </h4>

      {/* GPU info */}
      <Card bg="dark" text="light" className="border-secondary mb-4">
        <Card.Body className="py-2 px-3 d-flex align-items-center gap-3">
          <strong>GPU:</strong>
          {gpu.name ? (
            <>
              <span>{gpu.name}</span>
              <Badge bg="secondary">Compute {gpu.capability}</Badge>
            </>
          ) : (
            <span className="text-danger">No NVIDIA GPU detected</span>
          )}
        </Card.Body>
      </Card>

      {/* GPU utilisation metrics */}
      <GpuMetrics />

      {/* Compile progress */}
      {isCompiling && (
        <Card bg="dark" text="light" className="border-info mb-4">
          <Card.Body>
            <div className="d-flex justify-content-between mb-2">
              <span>
                <BsArrowRepeat className="me-2 spin-animation" />
                Compiling <strong>{compileProgress.model}</strong>
              </span>
              <span className="text-muted">{compileProgress.percent}%</span>
            </div>
            <ProgressBar
              now={compileProgress.percent}
              variant="info"
              animated
              striped
              label={compileProgress.status}
              style={{ height: 24 }}
            />
            <small className="text-muted mt-2 d-block">
              TensorRT compilation typically takes 5–15 minutes. Do not close the browser.
            </small>
          </Card.Body>
        </Card>
      )}

      {/* Compiled engines */}
      {engines.length > 0 && (
        <>
          <h6 className="text-light mb-2">Compiled Engines</h6>
          <Table variant="dark" bordered hover size="sm" className="mb-4">
            <thead>
              <tr>
                <th>Engine</th>
                <th>Source Model</th>
                <th>Size</th>
                <th style={{ width: 60 }}></th>
              </tr>
            </thead>
            <tbody>
              {engines.map(e => (
                <tr key={e.filename}>
                  <td className="font-monospace">{e.filename}</td>
                  <td>{e.source_model}</td>
                  <td>{e.size_mb} MB</td>
                  <td className="text-center">
                    <Button
                      variant="outline-danger"
                      size="sm"
                      disabled={isCompiling}
                      onClick={() => send('delete_engine', { filename: e.filename })}
                      title="Delete engine"
                    >
                      <BsTrash />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      )}

      {/* Available models to compile */}
      <h6 className="text-light mb-2">Available Models</h6>
      <p className="text-muted small mb-3">
        Select a YOLO model to compile into a TensorRT FP16 engine optimized for your GPU.
        Compiled engines appear in the camera detection settings.
      </p>
      <Table variant="dark" bordered hover size="sm">
        <thead>
          <tr>
            <th>Model</th>
            <th>Status</th>
            <th style={{ width: 120 }}></th>
          </tr>
        </thead>
        <tbody>
          {compilable_models.map(model => {
            const compiled = compiledSet.has(model);
            const currentlyCompiling = isCompiling && compileProgress.model === model;
            return (
              <tr key={model}>
                <td className="font-monospace">{model}</td>
                <td>
                  {compiled ? (
                    <Badge bg="success">Compiled</Badge>
                  ) : currentlyCompiling ? (
                    <Badge bg="info">Compiling...</Badge>
                  ) : (
                    <Badge bg="secondary">Not compiled</Badge>
                  )}
                </td>
                <td className="text-center">
                  {!compiled && !currentlyCompiling && (
                    <Button
                      variant="outline-info"
                      size="sm"
                      disabled={isCompiling || !gpu.name}
                      onClick={() => send('compile_engine', { model })}
                    >
                      Compile
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </div>
  );
}
