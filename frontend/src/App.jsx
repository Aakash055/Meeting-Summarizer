import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = 'https://meeting-summarizer-i9fm.onrender.com'

function App() {
  function renderSpacedText(text) {
    return text.split('').map((char, i) => (
      <span key={i}>{char === ' ' ? '\u00A0' : char}</span>
    ))
  }

  const [token, setToken] = useState(localStorage.getItem('token'))
  const [authView, setAuthView] = useState('login')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authError, setAuthError] = useState(null)
  const [isAuthLoading, setIsAuthLoading] = useState(false)

  const [view, setView] = useState('dashboard')
  const [selectedFile, setSelectedFile] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [meetings, setMeetings] = useState([])
  const [isLoadingMeetings, setIsLoadingMeetings] = useState(false)
  const [selectedMeeting, setSelectedMeeting] = useState(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [meetingPendingDelete, setMeetingPendingDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    if (view === 'dashboard' && token) {
      loadMeetings()
    }
  }, [view, token])

  function authHeaders() {
    return { Authorization: `Bearer ${token}` }
  }

  async function handleAuthSubmit(event) {
    event.preventDefault()
    setIsAuthLoading(true)
    setAuthError(null)

    const endpoint = authView === 'login' ? '/login' : '/register'

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Authentication failed')
      }

      localStorage.setItem('token', data.access_token)
      setToken(data.access_token)
      setAuthEmail('')
      setAuthPassword('')
    } catch (err) {
      setAuthError(err.message)
    } finally {
      setIsAuthLoading(false)
    }
  }

  function handleLogout() {
    localStorage.removeItem('token')
    setToken(null)
    setMeetings([])
    setResult(null)
    setSelectedMeeting(null)
    setView('dashboard')
  }

  async function loadMeetings() {
    setIsLoadingMeetings(true)
    try {
      const response = await fetch(`${API_BASE}/meetings`, { headers: authHeaders() })
      if (response.status === 401) {
        handleLogout()
        return
      }
      const data = await response.json()
      setMeetings(data)
    } catch (err) {
      console.error('Failed to load meetings:', err)
    } finally {
      setIsLoadingMeetings(false)
    }
  }

  async function openMeeting(meetingId) {
    setIsLoadingDetail(true)
    setSelectedMeeting(null)
    setView('detail')
    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingId}`, { headers: authHeaders() })
      if (!response.ok) {
        throw new Error('Meeting not found')
      }
      const data = await response.json()
      setSelectedMeeting(data)
    } catch (err) {
      console.error('Failed to load meeting:', err)
    } finally {
      setIsLoadingDetail(false)
    }
  }

  function confirmDelete(event, meeting) {
    event.stopPropagation()
    setMeetingPendingDelete(meeting)
  }

  function cancelDelete() {
    setMeetingPendingDelete(null)
  }

  async function performDelete() {
    if (!meetingPendingDelete) return

    setIsDeleting(true)
    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingPendingDelete.id}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })

      if (!response.ok) {
        throw new Error('Failed to delete meeting')
      }

      setMeetings((prev) => prev.filter((m) => m.id !== meetingPendingDelete.id))
      setMeetingPendingDelete(null)
    } catch (err) {
      console.error('Delete failed:', err)
    } finally {
      setIsDeleting(false)
    }
  }

  async function handleSearch(event) {
    event.preventDefault()
    if (!searchQuery.trim()) return

    setIsSearching(true)
    setHasSearched(true)
    try {
      const response = await fetch(`${API_BASE}/search?q=${encodeURIComponent(searchQuery)}`, {
        headers: authHeaders(),
      })
      const data = await response.json()
      setSearchResults(data)
    } catch (err) {
      console.error('Search failed:', err)
      setSearchResults([])
    } finally {
      setIsSearching(false)
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
        headers: authHeaders(),
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

  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  function renderResultsBlock(data) {
    return (
      <div className="results-section">
        <h2>Summary</h2>
        <p>{data.summary}</p>

        <h2>Key Points</h2>
        {data.key_points && data.key_points.length > 0 ? (
          <ul>
            {data.key_points.map((point, index) => (
              <li key={index}>{point}</li>
            ))}
          </ul>
        ) : (
          <p>No key points recorded.</p>
        )}

        <h2>Decisions</h2>
        {data.decisions.length === 0 ? (
          <p>No decisions recorded.</p>
        ) : (
          <ul>
            {data.decisions.map((decision, index) => (
              <li key={index}>{decision}</li>
            ))}
          </ul>
        )}

        <h2>Action Items</h2>
        {data.action_items.length === 0 ? (
          <p>No action items found.</p>
        ) : (
          <ul>
            {data.action_items.map((item, index) => (
              <li key={index}>
                <strong>{item.task}</strong> — Assigned to: {item.assignee}, Deadline: {item.deadline}
              </li>
            ))}
          </ul>
        )}

        <h2>Topics</h2>
        <p>{data.topics.join(', ')}</p>

        <h2>Timestamped Transcript</h2>
        <div className="transcript-box">
          {data.segments.map((segment, index) => (
            <p key={index} className="transcript-line">
              <span className="timestamp">[{formatTime(segment.start)}]</span> {segment.text}
            </p>
          ))}
        </div>
      </div>
    )
  }

  if (!token) {
    return (
      <div className="app-container auth-container">
        <div className="brand brand-hero">
          <span className="brand-title">NoteGrain</span>
          <span className="brand-subtitle">{renderSpacedText('Meeting Summarizer')}</span>
        </div>
        <div className="auth-box">
          <div className="auth-tabs">
            <button
              className={authView === 'login' ? 'nav-active' : ''}
              onClick={() => { setAuthView('login'); setAuthError(null) }}
            >
              Login
            </button>
            <button
              className={authView === 'register' ? 'nav-active' : ''}
              onClick={() => { setAuthView('register'); setAuthError(null) }}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleAuthSubmit} className="auth-form">
            <input
              type="email"
              placeholder="Email"
              value={authEmail}
              onChange={(e) => setAuthEmail(e.target.value)}
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
              required
            />
            <button type="submit" disabled={isAuthLoading}>
              {isAuthLoading ? 'Please wait...' : authView === 'login' ? 'Login' : 'Register'}
            </button>
          </form>

          {authError && <p className="error-message">{authError}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      <div className="nav-bar">
        <div className="brand">
          <span className="brand-title">NoteGrain</span>
          <span className="brand-subtitle">{renderSpacedText('Meeting Summarizer')}</span>
        </div>
        <div className="nav-buttons">
          <button
            className={view === 'dashboard' ? 'nav-active' : ''}
            onClick={() => setView('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={view === 'search' ? 'nav-active' : ''}
            onClick={() => setView('search')}
          >
            Search
          </button>
          <button
            className={view === 'upload' ? 'nav-active' : ''}
            onClick={() => setView('upload')}
          >
            Upload New
          </button>
          <button onClick={handleLogout}>Logout</button>
        </div>
      </div>

      {view === 'dashboard' && (
        <div className="dashboard-section">
          <h2>Your Meetings ({meetings.length})</h2>

          {isLoadingMeetings && <p>Loading meetings...</p>}

          {!isLoadingMeetings && meetings.length === 0 && (
            <div className="empty-state">
              <p className="empty-state-title">No meetings yet</p>
              <p className="empty-state-subtitle">Upload your first recording to get a summary, action items, and a searchable transcript.</p>
              <button onClick={() => setView('upload')}>Upload a Recording</button>
            </div>
          )}

          <div className="meetings-list">
            {meetings.map((meeting) => (
              <div
                key={meeting.id}
                className="meeting-card meeting-card-clickable"
                onClick={() => openMeeting(meeting.id)}
              >
                <div className="meeting-card-header">
                  <strong>{meeting.filename}</strong>
                  <div className="meeting-card-actions">
                    <span className={`status-badge status-${meeting.status}`}>
                      {meeting.status}
                    </span>
                    <button
                      className="delete-button"
                      onClick={(e) => confirmDelete(e, meeting)}
                      title="Delete meeting"
                    >
                      ✕
                    </button>
                  </div>
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

      {view === 'search' && (
        <div className="search-section">
          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              placeholder="Search across all your transcripts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button type="submit" disabled={isSearching}>
              {isSearching ? 'Searching...' : 'Search'}
            </button>
          </form>

          {hasSearched && !isSearching && searchResults.length === 0 && (
            <p>No matches found for "{searchQuery}".</p>
          )}

          <div className="search-results-list">
            {searchResults.map((res, index) => (
              <div
                key={index}
                className="search-result-card"
                onClick={() => openMeeting(res.meeting_id)}
              >
                <div className="search-result-header">
                  <strong>{res.meeting_filename}</strong>
                  <span className="timestamp">[{formatTime(res.start_time)}]</span>
                </div>
                <p className="search-result-text">{res.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'detail' && (
        <div className="detail-view">
          <button className="back-button" onClick={() => setView('dashboard')}>
            ← Back to Dashboard
          </button>

          {isLoadingDetail && <p>Loading meeting details...</p>}

          {!isLoadingDetail && !selectedMeeting && (
            <p className="error-message">Could not load this meeting.</p>
          )}

          {!isLoadingDetail && selectedMeeting && (
            <>
              <h2 className="detail-filename">{selectedMeeting.filename}</h2>
              <p className="meeting-date">{formatDate(selectedMeeting.created_at)}</p>
              {renderResultsBlock(selectedMeeting)}
            </>
          )}
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

          {result && renderResultsBlock(result)}
        </div>
      )}

      {meetingPendingDelete && (
        <div className="modal-overlay" onClick={cancelDelete}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h3>Delete meeting?</h3>
            <p>This will permanently delete "{meetingPendingDelete.filename}" and all its data. This cannot be undone.</p>
            <div className="modal-actions">
              <button onClick={cancelDelete} disabled={isDeleting}>Cancel</button>
              <button onClick={performDelete} className="danger-button" disabled={isDeleting}>
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
