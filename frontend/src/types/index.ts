export interface TranscriptionResponse {
  id: string
  status: 'processing' | 'completed' | 'failed'
  text: string
  language: string
  confidence?: number
  duration?: number
  createdAt: string
  updatedAt: string
}

export interface TranscriptionRequest {
  audio_data: string | File
  language: string
  model?: string
}

export interface HealthResponse {
  status: 'ok' | 'error'
  message: string
}

export interface AuthResponse {
  success: boolean
  message: string
}
