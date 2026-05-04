import React, { useState, useRef } from 'react'
import { Box, Button, Typography } from '@mui/material'
import MicIcon from '@mui/icons-material/Mic'
import StopIcon from '@mui/icons-material/Stop'

interface AudioRecorderProps {
  onRecordingComplete: (blob: Blob) => void
  isLoading: boolean
}

export default function AudioRecorder({ onRecordingComplete, isLoading }: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      
      chunksRef.current = []
      mediaRecorderRef.current = mediaRecorder

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        onRecordingComplete(blob)
        stream.getTracks().forEach(track => track.stop())
      }

      mediaRecorder.start()
      setIsRecording(true)
      setRecordingTime(0)

      timerRef.current = setInterval(() => {
        setRecordingTime((prev: number) => prev + 1)
      }, 1000)
    } catch (error) {
      console.error('Error accessing microphone:', error)
      alert('Unable to access microphone. Please check permissions.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <Box
      sx={{
        border: '1px solid #2a2a4a',
        borderRadius: 3,
        padding: 3,
        textAlign: 'center',
        backgroundColor: '#111119'
      }}
    >
      <Typography variant="h6" sx={{ mb: 2, color: '#ffffff' }}>
        Record Audio
      </Typography>

      {isRecording && (
        <Typography variant="body2" sx={{ mb: 2, fontWeight: 'bold', color: '#e94560' }}>
          Recording: {formatTime(recordingTime)}
        </Typography>
      )}

      <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
        {!isRecording ? (
          <Button
            variant="contained"
            sx={{ backgroundColor: '#e94560', '&:hover': { backgroundColor: '#c73652' } }}
            startIcon={<MicIcon />}
            onClick={startRecording}
            disabled={isLoading}
          >
            Start Recording
          </Button>
        ) : (
          <Button
            variant="contained"
            sx={{ backgroundColor: '#2a2a4a', '&:hover': { backgroundColor: '#3d3c56' } }}
            startIcon={<StopIcon />}
            onClick={stopRecording}
          >
            Stop Recording
          </Button>
        )}
      </Box>
    </Box>
  )
}
