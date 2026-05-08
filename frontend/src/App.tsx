import React, { useEffect, useState, useRef } from 'react'
import './index.css'
import { checkHealth, verifyToken, getSettings, updateSettings, createJob, initUpload, uploadChunk, completeUpload, getJobStatus, getTranscript, listJobs } from './api'
import type { TranscriptionResponse } from './types'

const SUPPORTED_FILE_REGEX = /\.(mp3|mp4)$/i
const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024
const CHUNK_SIZE = 1024 * 1024 * 5 // 5MB chunks
const POLL_INTERVAL = 3000 // 3 seconds

function formatBytes(bytes: number) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}


function App() {
  const [authorized, setAuthorized] = useState(false)
  const [isHealthy, setIsHealthy] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [language, setLanguage] = useState('en-IN')
  const [transcription, setTranscription] = useState<TranscriptionResponse | null>(null)
  const [editedText, setEditedText] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileInfoVisible, setFileInfoVisible] = useState(false)
  const [jobStatus, setJobStatus] = useState('No active job')
  const [statusBadgeClass, setStatusBadgeClass] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [authToken, setAuthToken] = useState<string>('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sarvamApiKey, setSarvamApiKey] = useState('')
  const [settingsStatus, setSettingsStatus] = useState('')
  const [settingsStatusType, setSettingsStatusType] = useState<'success' | 'error' | ''>('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [jobHistory, setJobHistory] = useState<Array<{ id: string; status: string; language: string; file_size?: number; duration_seconds?: number; created_at: string; error_message?: string }>>([])
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const pollingIntervalRef = useRef<number | null>(null)

  useEffect(() => {
    const authToken = cookieStore.get('_auth')
    authToken.then(async (token) => {
      if (token == null || token.value == null) {
        // For development: set a dummy token
        if (import.meta.env.DEV) {
          setAuthToken('dev-token')
          setAuthorized(true)
        } else {
          window.location.href = 'https://ems.beqisoft.net/login'
        }
        return
      }
      try {
        await verifyToken(token.value)
        setAuthToken(token.value)
        setAuthorized(true)
      } catch (err) {
        window.location.href = 'https://ems.beqisoft.net/login'
      }
    }).catch(() => {
      // For development: set a dummy token
      if (import.meta.env.DEV) {
        setAuthToken('dev-token')
        setAuthorized(true)
      } else {
        window.location.href = 'https://ems.beqisoft.net/login'
      }
    })
  }, [])

  useEffect(() => {
    const checkHealthStatus = async () => {
      const healthy = await checkHealth()
      setIsHealthy(healthy)
    }

    checkHealthStatus()
    const interval = setInterval(checkHealthStatus, 15000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const data = await getSettings()
        if (data && data.sarvam_api_key) {
          setSarvamApiKey(data.sarvam_api_key)
        }
      } catch (err) {
        console.warn('Could not load settings:', err)
      }
    }

    loadSettings()
  }, [])

  const pollJobStatus = async (jobId: string) => {
    try {
      const status = await getJobStatus(jobId)
      setJobStatus(getStatusLabel(status.status))
      setStatusBadgeClass(status.status)

      if (status.status === 'completed') {
        // Stop polling and fetch transcript
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
        }
        try {
          const transcript = await getTranscript(jobId)
          setTranscription({
            id: jobId,
            status: 'completed',
            text: transcript.full_text || '',
            language: language,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
          })
          setIsLoading(false)
        } catch (err) {
          console.error('Failed to fetch transcript:', err)
          setError('Failed to retrieve transcript')
          setJobStatus('Failed')
          setStatusBadgeClass('failed')
          setIsLoading(false)
        }
      } else if (status.status === 'failed') {
        // Stop polling on failure
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
        }
        setError(status.error_message || 'Transcription failed')
        setJobStatus('Failed')
        setStatusBadgeClass('failed')
        setIsLoading(false)
      }
    } catch (err) {
      console.error('Polling error:', err)
    }
  }

  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (transcription) {
      setEditedText(transcription.text)
    }
  }, [transcription])

  const handleFileSelect = async (file: File) => {
    if (!SUPPORTED_FILE_REGEX.test(file.name)) {
      alert('Unsupported file format. Please use MP3 or MP4.')
      return
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      alert('File too large. Maximum is 500 MB.')
      return
    }

    setSelectedFile(file)
    setFileInfoVisible(true)
    setJobStatus('Ready to transcribe')
    setStatusBadgeClass('queued')
    setError(null)
  }

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      handleFileSelect(file)
    }
  }

  const handleUploadZoneClick = () => {
    fileInputRef.current?.click()
  }

  const handleUploadStart = async () => {
    if (!selectedFile) {
      alert('No file selected')
      return
    }
    if (!isHealthy) {
      alert('Backend is offline')
      return
    }

    setIsLoading(true)
    setJobStatus('Creating job...')
    setStatusBadgeClass('queued')
    setError(null)
    setUploadProgress(0)

    try {
      // Step 1: Create job
      const jobResponse = await createJob({ language, mode: 'batch' })
      const jobId = jobResponse.id
      setCurrentJobId(jobId)
      setJobStatus('Initializing upload...')

      // Step 2: Initialize upload
      const fileSize = selectedFile.size
      const totalChunks = Math.ceil(fileSize / CHUNK_SIZE)
      await initUpload(jobId, totalChunks, fileSize)
      setJobStatus('Uploading file...')
      setStatusBadgeClass('uploading_to_sarvam')

      // Step 3: Upload chunks
      let uploadedChunks = 0
      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE
        const end = Math.min(start + CHUNK_SIZE, fileSize)
        const chunkBlob = selectedFile.slice(start, end)

        await uploadChunk(jobId, i, chunkBlob)
        uploadedChunks++
        const progress = Math.round((uploadedChunks / totalChunks) * 100)
        setUploadProgress(progress)
      }

      // Step 4: Complete upload
      setJobStatus('Finalizing upload...')
      await completeUpload(jobId)
      setJobStatus('Processing...')
      setStatusBadgeClass('sarvam_processing')

      // Step 5: Start polling for job status
      pollingIntervalRef.current = setInterval(() => {
        pollJobStatus(jobId)
      }, POLL_INTERVAL)

      // Initial poll
      await pollJobStatus(jobId)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed'
      setError(errorMessage)
      setJobStatus('Failed')
      setStatusBadgeClass('failed')
      setIsLoading(false)
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
      }
    }
  }

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragActive(false)
    const file = event.dataTransfer.files?.[0]
    if (file) {
      handleFileSelect(file)
    }
  }

  const handleEdit = () => {
    if (!transcription) return
    setIsEditing(true)
  }

  const handleSaveEdit = () => {
    if (!transcription) return
    setTranscription({ ...transcription, text: editedText })
    setIsEditing(false)
  }

  const handleCancelEdit = () => {
    setEditedText(transcription?.text || '')
    setIsEditing(false)
  }

  const handleDownloadTxt = () => {
    if (!transcription) return
    const blob = new Blob([transcription.text], { type: 'text/plain' })
    const element = document.createElement('a')
    element.href = URL.createObjectURL(blob)
    element.download = `transcription_${new Date().toISOString().split('T')[0]}.txt`
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  const openSettings = () => {
    setSettingsOpen(true)
    setSettingsStatus('')
    setSettingsStatusType('')
  }

  const closeSettings = () => {
    setSettingsOpen(false)
    setSettingsStatus('')
    setSettingsStatusType('')
  }

  const saveSettings = async () => {
    setSettingsStatus('Applying...')
    setSettingsStatusType('')
    try {
      await updateSettings({ sarvam_api_key: sarvamApiKey.trim() })
      setSettingsStatus('✓ API key saved!')
      setSettingsStatusType('success')
      setTimeout(() => {
        setSettingsStatus('')
        setSettingsStatusType('')
        closeSettings()
      }, 2000)
    } catch (err) {
      setSettingsStatus('Failed: ' + (err instanceof Error ? err.message : 'Backend offline'))
      setSettingsStatusType('error')
    }
  }

  const handleSettingsOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      closeSettings()
    }
  }

  const toggleHistory = () => {
    setHistoryOpen((open) => !open)
    if (!historyOpen) {
      loadJobHistory()
    }
  }

  const loadJobHistory = async () => {
    try {
      const result = await listJobs(1, 50)
      setJobHistory(result.jobs)
    } catch (err) {
      console.error('Failed to load job history:', err)
    }
  }

  const getStatusLabel = (status: string): string => {
    const labels: { [key: string]: string } = {
      queued: 'Queued',
      uploading_to_sarvam: 'Uploading to Sarvam...',
      sarvam_processing: 'Processing...',
      downloading_result: 'Retrieving transcript...',
      completed: 'Completed',
      failed: 'Failed'
    }
    return labels[status] || status
  }

  const handleHistoryItemClick = async (jobId: string) => {
    try {
      const status = await getJobStatus(jobId)
      if (status.status === 'completed') {
        const transcript = await getTranscript(jobId)
        setTranscription({
          id: jobId,
          status: 'completed',
          text: transcript.full_text || '',
          language: language,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        })
      }
    } catch (err) {
      console.error('Failed to load transcript:', err)
    }
  }

  if (!authorized) {
    return (
      <div className="app" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div className="loading">Loading...</div>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1 className="logo">Audio to Text</h1>
          <span className="subtitle">Audio to Text</span>
        </div>
        <div className="header-right">
          <select
            id="languageSelect"
            className="language-select"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="en-IN">English (India)</option>
            <option value="hi-IN">Hindi</option>
            <option value="ta-IN">Tamil</option>
            <option value="te-IN">Telugu</option>
            <option value="kn-IN">Kannada</option>
            <option value="ml-IN">Malayalam</option>
            <option value="mr-IN">Marathi</option>
            <option value="gu-IN">Gujarati</option>
            <option value="bn-IN">Bengali</option>
            <option value="pa-IN">Punjabi</option>
            <option value="od-IN">Odia</option>
            <option value="as-IN">Assamese</option>
            <option value="ur-IN">Urdu</option>
            <option value="ne-IN">Nepali</option>
            <option value="unknown">Auto-detect</option>
          </select>
          <div className="backend-status">
            <span className={`status-dot ${isHealthy ? 'connected' : 'disconnected'}`} />
            <span className="status-text">{isHealthy ? 'Online' : 'Offline'}</span>
          </div>
          <button className="settings-btn" title="Settings" type="button" onClick={openSettings}>
            ⚙
          </button>
        </div>
      </header>

      <div className={`settings-overlay ${settingsOpen ? '' : 'hidden'}`} onClick={handleSettingsOverlayClick}>
        <div className="settings-modal">
          <div className="settings-header">
            <h2>Settings</h2>
            <button className="close-btn" type="button" onClick={closeSettings}>
              ✕
            </button>
          </div>
          <div className="settings-body">
            <div className="settings-group">
              <label htmlFor="sarvamApiKey">Sarvam AI API Key</label>
              <input
                id="sarvamApiKey"
                type="password"
                value={sarvamApiKey}
                placeholder="Enter your Sarvam API key..."
                autoComplete="off"
                onChange={(e) => setSarvamApiKey(e.target.value)}
              />
              <p className="settings-hint">
                Get your key from{' '}
                <a href="https://dashboard.sarvam.ai" target="_blank" rel="noreferrer">
                  dashboard.sarvam.ai
                </a>
              </p>
            </div>
            <div className={`settings-status ${settingsStatusType}`}>{settingsStatus}</div>
          </div>
          <div className="settings-footer">
            <button className="btn-save-settings" type="button" onClick={saveSettings}>
              Save &amp; Apply
            </button>
          </div>
        </div>
      </div>

      <div className="main-layout">
        <div className="left-panel">
          <div className="source-tabs">
            <button className="tab-btn active" type="button" onClick={handleUploadZoneClick}>
              Upload File
            </button>
          </div>

          <div className="source-panel" id="filePanel">
            <div
              className={`upload-zone ${dragActive ? 'drag-over' : ''} ${fileInfoVisible ? 'hidden' : ''}`}
              id="uploadZone"
              onClick={handleUploadZoneClick}
              onDragEnter={() => setDragActive(true)}
              onDragOver={(e) => {
                e.preventDefault();
                setDragActive(true)
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
            >
              <div className="upload-icon">📁</div>
              <p>Drag & drop audio file or click to browse</p>
              <p className="upload-limits">MP3, MP4</p>
              <input
                ref={fileInputRef}
                type="file"
                id="fileInput"
                hidden
                accept=".mp3,.mp4,audio/mpeg,audio/mp4,video/mp4"
                onChange={handleFileInputChange}
              />
            </div>

            <div className={`file-info ${fileInfoVisible ? '' : 'hidden'}`} id="fileInfo">
              <div className="file-detail">
                <span>{selectedFile?.name}</span>
                <span>{selectedFile ? formatBytes(selectedFile.size) : ''}</span>
                <span>—</span>
              </div>
              <div className="upload-progress" id="uploadProgress">
                <div className="progress-bar">
                  <div className="progress-fill" id="progressFill" style={{ width: `${uploadProgress}%` }} />
                </div>
                <span className="progress-text" id="progressText">{isLoading ? `${uploadProgress}%` : 'Ready'}</span>
              </div>
              <button className="ctrl-btn record-btn" id="uploadStartBtn" type="button" onClick={handleUploadStart} disabled={!selectedFile || isLoading || !isHealthy}>
                {isLoading ? 'Transcribing...' : 'Start Transcription'}
              </button>
            </div>
          </div>

          <div className="job-status" id="jobStatus">
            <div className={`status-badge ${statusBadgeClass}`}>{jobStatus}</div>
          </div>
        </div>

        <div className="right-panel">
          <div className="transcript-header">
            <h2>Transcript</h2>
            <div className="transcript-actions">
              <button className="action-btn" id="editToggle" type="button" onClick={handleEdit} disabled={!transcription || isLoading}>
                Edit
              </button>
              <button className="action-btn" id="saveEdit" type="button" onClick={handleSaveEdit} hidden={!isEditing}>
                Save
              </button>
              <button className="action-btn" id="cancelEdit" type="button" onClick={handleCancelEdit} hidden={!isEditing}>
                Cancel
              </button>
            </div>
          </div>

          <div className="transcript-content" id="transcriptContent">
            <div className={`empty-state ${transcription || isLoading ? 'hidden' : ''}`} id="emptyState">
              <p>Upload a file to see the transcription here.</p>
            </div>
            <div className={`loading-state ${isLoading ? '' : 'hidden'}`} id="loadingState">
              <p style={{ marginBottom: '10px', fontWeight: 'bold' }}>Uploading to SARVAM AI...</p>
              <p style={{ fontSize: '14px', color: '#888' }}>{jobStatus}</p>
              {uploadProgress > 0 && uploadProgress < 100 && (
                <p style={{ fontSize: '12px', marginTop: '8px' }}>Upload Progress: {uploadProgress}%</p>
              )}
            </div>
            <div className={`live-transcript ${transcription && !isEditing ? '' : 'hidden'}`} id="liveTranscript">
              {transcription?.text}
            </div>
            <textarea
              className={`edit-area ${isEditing ? '' : 'hidden'}`}
              id="editArea"
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
            />
          </div>

          <div className="download-bar">
            <span className="download-label">Download:</span>
            <button className="download-btn" id="downloadTxt" type="button" onClick={handleDownloadTxt} disabled={!transcription}>
              TXT
            </button>
          </div>
        </div>
      </div>

      <div className={`history-sidebar ${historyOpen ? '' : 'hidden'}`} id="historySidebar">
        <div className="sidebar-header">
          <h2>History</h2>
          <button className="close-btn" id="closeHistory" type="button" onClick={toggleHistory}>
            ✕
          </button>
        </div>
        <div className="history-list" id="historyList">
          {jobHistory.length === 0 ? (
            <div className="loading">No history available</div>
          ) : (
            jobHistory.map((job) => (
              <div
                key={job.id}
                className={`history-item status-${job.status}`}
                style={{ cursor: 'pointer', padding: '10px', marginBottom: '8px', borderRadius: '4px', backgroundColor: '#f5f5f5', border: '1px solid #ddd' }}
                onClick={() => handleHistoryItemClick(job.id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#333' }}>
                    {new Date(job.created_at).toLocaleTimeString()}
                  </span>
                  <span
                    style={{
                      fontSize: '10px',
                      padding: '2px 6px',
                      borderRadius: '3px',
                      backgroundColor:
                        job.status === 'completed'
                          ? '#d4edda'
                          : job.status === 'failed'
                            ? '#f8d7da'
                            : job.status === 'uploading_to_sarvam'
                              ? '#fff3cd'
                              : '#e7e7e7',
                      color:
                        job.status === 'completed'
                          ? '#155724'
                          : job.status === 'failed'
                            ? '#721c24'
                            : job.status === 'uploading_to_sarvam'
                              ? '#856404'
                              : '#666'
                    }}
                  >
                    {getStatusLabel(job.status)}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: '#666' }}>
                  {job.duration_seconds && `${Math.round(job.duration_seconds / 60)} min · `}
                  {job.file_size && `${(job.file_size / (1024 * 1024)).toFixed(1)} MB`}
                  {job.language && ` · ${job.language}`}
                </div>
                {job.error_message && (
                  <div style={{ fontSize: '11px', color: '#721c24', marginTop: '4px' }}>
                    {job.error_message}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <button className="history-toggle" id="historyToggle" type="button" onClick={toggleHistory}>
        History
      </button>
    </div>
  )
}

export default App
