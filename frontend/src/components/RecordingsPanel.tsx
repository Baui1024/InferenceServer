import { useEffect } from 'react';
import { Card, Button, Table } from 'react-bootstrap';
import { BsPlayFill, BsTrash, BsDownload, BsCameraReels } from 'react-icons/bs';
import { useCameras } from '../context/CameraContext';

export default function RecordingsPanel() {
  const { recordings, send, serverConfig } = useCameras();

  useEffect(() => {
    send('list_recordings');
  }, [send]);

  if (!serverConfig.recording_enabled) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100 text-muted">
        <div className="text-center">
          <BsCameraReels size={48} className="mb-3 opacity-50" />
          <p>Recording is not enabled.</p>
          <p className="small">Start the server with <code>--record</code> flag or set <code>RECORDING_ENABLED=1</code></p>
        </div>
      </div>
    );
  }

  const handleDelete = (rec: { id: string }) => {
    if (confirm(`Delete recording "${rec.id}"?`)) {
      send('delete_recording', { id: rec.id });
    }
  };

  const handlePlay = (rec: { id: string }) => {
    send('play_recording', { recording_id: rec.id });
  };

  const formatDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.round(s % 60);
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <div className="p-3 overflow-auto h-100" data-bs-theme="dark">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h5 className="mb-0">Recordings</h5>
        <Button variant="outline-light" size="sm" onClick={() => send('list_recordings')}>
          Refresh
        </Button>
      </div>

      {recordings.length === 0 ? (
        <Card bg="dark" border="secondary" className="text-center p-4">
          <Card.Body className="text-muted">
            <BsCameraReels size={36} className="mb-2 opacity-50" />
            <p className="mb-0">No recordings yet.</p>
            <p className="small">Use the record button on a camera stream to capture video.</p>
          </Card.Body>
        </Card>
      ) : (
        <Table variant="dark" hover responsive size="sm">
          <thead>
            <tr>
              <th>Camera</th>
              <th>Date</th>
              <th>Duration</th>
              <th>Frames</th>
              <th>Resolution</th>
              <th>Size</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {recordings.map(rec => (
              <tr key={rec.id}>
                <td>
                  <span className="fw-semibold">{rec.camera_name}</span>
                </td>
                <td className="small text-nowrap">{formatTime(rec.start_time)}</td>
                <td>{formatDuration(rec.duration_s)}</td>
                <td className="font-monospace">{rec.frame_count}</td>
                <td className="font-monospace small">
                  {rec.resolution ? `${rec.resolution[0]}x${rec.resolution[1]}` : '-'}
                </td>
                <td className="font-monospace">{rec.size_mb ?? '-'} MB</td>
                <td>
                  <div className="d-flex gap-1 justify-content-end">
                    <Button
                      variant="outline-success" size="sm"
                      onClick={() => handlePlay(rec)}
                      title="Play — opens as a camera, change model in Detection settings"
                    >
                      <BsPlayFill />
                    </Button>
                    <Button
                      variant="outline-light" size="sm"
                      as="a"
                      href={`/recordings/${rec.filename}`}
                      title="Download"
                    >
                      <BsDownload />
                    </Button>
                    <Button
                      variant="outline-danger" size="sm"
                      onClick={() => handleDelete(rec)}
                      title="Delete"
                    >
                      <BsTrash />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
