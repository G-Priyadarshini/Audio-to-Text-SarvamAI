import type { HealthResponse, AuthResponse } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'
const BACKEND_BASE_URL = API_BASE_URL.endsWith('/api') 
  ? API_BASE_URL.slice(0, -4) 
  : API_BASE_URL

// ── Auth ──
export async function verifyToken(authToken: string): Promise<AuthResponse> {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`
    }
    
    const response = await fetch(`${API_BASE_URL}/auth/verify`, {
      method: 'GET',
      headers
    })

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Unauthorized: Invalid or expired token')
      }
      const errorData = await response.json().catch(async () => ({ error: await response.text() }))
      throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Token verification failed')
  }
}

// ── Health Check ──
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    const data: HealthResponse = await response.json()
    return data.status === 'ok'
  } catch (error) {
    console.error('Health check failed:', error)
    return false
  }
}

// ── Settings ──
export async function getSettings(): Promise<{ sarvam_api_key: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/settings`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })

    if (!response.ok) {
      throw new Error(`Failed to load settings: ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Could not load settings')
  }
}

export async function updateSettings(data: { sarvam_api_key: string | null }): Promise<{ message: string; sarvam_api_key_set: boolean }> {
  try {
    const response = await fetch(`${API_BASE_URL}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })

    if (!response.ok) {
      const errorData = await response.json().catch(async () => ({ error: await response.text() }))
      throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Could not save settings')
  }
}

// ── Jobs (Batch Transcription) ──
export async function createJob(params: { language?: string; mode: string }): Promise<{ id: string; status: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    })

    if (!response.ok) {
      const errorData = await response.json().catch(async () => ({ error: await response.text() }))
      throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Failed to create job')
  }
}

export async function getJobStatus(jobId: string): Promise<{ id: string; status: string; error_message?: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })

    if (!response.ok) {
      throw new Error(`Failed to get job status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Status check failed')
  }
}

export async function getTranscript(jobId: string): Promise<{ full_text: string; diarized_json?: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/transcript`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })

    if (!response.ok) {
      throw new Error(`Failed to get transcript: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Failed to get transcript')
  }
}

// ── Upload Initialization ──
export async function initUpload(jobId: string, totalChunks: number, fileSize: number): Promise<{ job_id: string; total_chunks: number }> {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/upload/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ total_chunks: totalChunks, file_size: fileSize })
    })

    if (!response.ok) {
      const errorData = await response.json().catch(async () => ({ error: await response.text() }))
      throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Failed to init upload')
  }
}

// ── Upload Chunk ──
export async function uploadChunk(jobId: string, chunkIndex: number, chunkBlob: Blob): Promise<{ message: string }> {
  try {
    const formData = new FormData()
    formData.append('file', chunkBlob)

    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/upload/chunks/${chunkIndex}`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      const errorData = await response.json().catch(async () => ({ error: await response.text() }))
      throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Failed to upload chunk')
  }
}

// ── Upload Complete ──
export async function completeUpload(jobId: string): Promise<{ job_id: string; status: string; message: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/upload/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })

    if (!response.ok) {
      const errorData = await response.json().catch(async () => ({ error: await response.text() }))
      throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw error instanceof Error ? error : new Error('Failed to complete upload')
  }
}
