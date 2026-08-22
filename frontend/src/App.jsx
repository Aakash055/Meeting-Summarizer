import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = 'http://127.0.0.1:8000'

function App() {
  const [view, setView] = useState('dashboard')
  const [selectedFile, setSelectedFile] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [meetings, setMeetings] = useState([])
  const [isLoadingMeetings, setIsLoadingMeetings] = useState(false)

  useEffect(() => {
    if (view === 'dashboard') {
      loadMeetings()
    }
  }, [view])

  async function loadMeetings() {
    setIsLoadingMeetings(true)
    try {
      const response = await fetch(`${API_BASE}/meetings`)
      const data = await response.json()
      setMeetings(data)
    } catch (err) {
      console.error('Failed to load meetings:', err)
    } finally {
      setIsLoadingMeetings(false)
    }
  }

  function handleFileChange(event) {
    setSelectedFile(event.target.files[0])
    setResult(null)
    setError(null)
  }

  async function handleUpload() {
    if (!selectedFile) {
      setError('Please select a file first.')
      return
    }

    setIsUploading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsUploading(false)
    }
  }

  function formatDate(isoString) {
    const date = new Date(isoString)
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="app-container">
      <div className="nav-bar">
        <h1>Meeting Summarizer</h1>
        <div className="nav-buttons">
          <button
            className={view === 'dashboard' ? 'nav-active' : ''}
            onClick={() => setView('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={view === 'upload' ? 'nav-active' : ''}
            onClick={() => setView('upload')}
          >
            Upload New
          </button>
        </div>
      </div>

      {view === 'dashboard' && (
        <div className="dashboard-section">
          <h2>Your Meetings ({meetings.length})</h2>

          {isLoadingMeetings && <p>Loading meetings...</p>}

          {!isLoadingMeetings && meetings.length === 0 && (
            <p>No meetings yet. Upload your first recording to get started.</p>
          )}

          <div className="meetings-list">
            {meetings.map((meeting) => (
              <div key={meeting.id} className="meeting-card">
                <div className="meeting-card-header">
                  <strong>{meeting.filename}</strong>
                  <span className={`status-badge status-${meeting.status}`}>
                    {meeting.status}
                  </span>
                </div>
                <p className="meeting-date">{formatDate(meeting.created_at)}</p>
                <p className="meeting-summary-preview">
                  {meeting.summary ? meeting.summary.slice(0, 150) + '...' : 'No summary available.'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'upload' && (
        <div className="upload-view">
          <div className="upload-section">
            <input type="file" accept="audio/*,video/*" onChange={handleFileChange} disabled={isUploading} />
            <button onClick={handleUpload} disabled={isUploading}>
              {isUploading ? 'Processing...' : 'Upload & Summarize'}
            </button>
          </div>

          {isUploading && (
            <div className="processing-indicator">
              <div className="spinner"></div>
              <p>Transcribing and analyzing your file — this can take a moment for longer recordings.</p>
            </div>
          )}

          {error && <p className="error-message">{error}</p>}

          {result && (
            <div className="results-section">
              <h2>Summary</h2>
              <p>{result.summary}</p>

              <h2>Key Points</h2>
              <ul>
                {result.key_points.map((point, index) => (
                  <li key={index}>{point}</li>
                ))}
              </ul>

              <h2>Decisions</h2>
              {result.decisions.length === 0 ? (
                <p>No decisions recorded.</p>
              ) : (
                <ul>
                  {result.decisions.map((decision, index) => (
                    <li key={index}>{decision}</li>
                  ))}
                </ul>
              )}

              <h2>Action Items</h2>
              {result.action_items.length === 0 ? (
                <p>No action items found.</p>
              ) : (
                <ul>
                  {result.action_items.map((item, index) => (
                    <li key={index}>
                      <strong>{item.task}</strong> — Assigned to: {item.assignee}, Deadline: {item.deadline}
                    </li>
                  ))}
                </ul>
              )}

              <h2>Topics</h2>
              <p>{result.topics.join(', ')}</p>

              <h2>Timestamped Transcript</h2>
              <div className="transcript-box">
                {result.segments.map((segment, index) => (
                  <p key={index} className="transcript-line">
                    <span className="timestamp">[{formatTime(segment.start)}]</span> {segment.text}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export default App