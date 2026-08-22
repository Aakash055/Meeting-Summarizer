import { useState } from 'react'
import './App.css'

function App() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

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
      const response = await fetch('http://127.0.0.1:8000/upload', {
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

  return (
    <div className="app-container">
      <h1>Meeting Summarizer</h1>

      <div className="upload-section">
        <input type="file" accept="audio/*,video/*" onChange={handleFileChange} />
        <button onClick={handleUpload} disabled={isUploading}>
          {isUploading ? 'Processing...' : 'Upload & Summarize'}
        </button>
      </div>

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
        </div>
      )}
    </div>
  )
}

export default App