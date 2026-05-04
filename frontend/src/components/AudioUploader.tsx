import React, { useState } from 'react'
import { Box, Button, CircularProgress, Typography } from '@mui/material'
import CloudUploadIcon from '@mui/icons-material/CloudUpload'

interface AudioUploaderProps {
  onUpload: (file: File) => void
  isLoading: boolean
}

export default function AudioUploader({ onUpload, isLoading }: AudioUploaderProps) {
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    const files = e.dataTransfer.files
    if (files && files[0]) {
      handleFile(files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files[0]) {
      handleFile(files[0])
    }
  }

  const handleFile = (file: File) => {
    const validTypes = ['audio/mp3', 'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm']
    if (!validTypes.includes(file.type)) {
      alert('Please upload a valid audio file (MP3, WAV, OGG, WebM)')
      return
    }
    onUpload(file)
  }

  return (
    <Box>
      <Button
        variant="contained"
        fullWidth
        sx={{ mb: 3, py: 1.5, fontWeight: 700, backgroundColor: '#e94560', '&:hover': { backgroundColor: '#c73652' } }}
        onClick={() => fileInputRef.current?.click()}
        disabled={isLoading}
      >
        Upload File
      </Button>

      <Box
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        sx={{
          border: '1px dashed',
          borderColor: dragActive ? '#e94560' : '#2a2a4a',
          borderRadius: 3,
          padding: 5,
          textAlign: 'center',
          cursor: 'pointer',
          backgroundColor: dragActive ? '#161426' : '#111119',
          transition: 'all 0.3s ease',
          '&:hover': {
            borderColor: '#e94560',
            backgroundColor: '#161426'
          }
        }}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          onChange={handleChange}
          style={{ display: 'none' }}
          disabled={isLoading}
        />

        <Box sx={{ mb: 2 }}>
          <CloudUploadIcon sx={{ fontSize: 52, color: '#e94560' }} />
        </Box>

        <Typography variant="h6" sx={{ mb: 1, color: '#ffffff' }}>
          Drag and drop audio here
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          or click to browse
        </Typography>
        <Typography variant="body2" color="text.secondary">
          MP3, WAV, OGG, WebM
        </Typography>

        {isLoading && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mt: 3 }}>
            <CircularProgress size={24} />
            <Typography color="#ffffff">Processing...</Typography>
          </Box>
        )}
      </Box>
    </Box>
  )
}
