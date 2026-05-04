import React, { useState } from 'react'
import { Box, Button, TextField, Typography, Paper } from '@mui/material'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import DownloadIcon from '@mui/icons-material/Download'

interface TranscriptionResultProps {
  text: string
  isEditing: boolean
  onEditToggle: () => void
  onSave: (text: string) => void
  onDownload: () => void
}

export default function TranscriptionResult({
  text,
  isEditing,
  onEditToggle,
  onSave,
  onDownload
}: TranscriptionResultProps) {
  const [editedText, setEditedText] = useState(text)

  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    alert('Copied to clipboard!')
  }

  const handleSave = () => {
    onSave(editedText)
    onEditToggle()
  }

  if (!text) {
    return (
      <Paper sx={{ padding: 3, textAlign: 'center', backgroundColor: '#111119', border: '1px solid #2a2a4a' }}>
        <Typography color="text.secondary">
          Upload an audio file to see the transcription here.
        </Typography>
      </Paper>
    )
  }

  return (
    <Paper sx={{ padding: 3, backgroundColor: '#111119', border: '1px solid #2a2a4a' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h6" sx={{ color: '#ffffff' }}>
          Transcription Result
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button size="small" variant="contained" sx={{ backgroundColor: '#2a2a4a', color: '#ffffff', '&:hover': { backgroundColor: '#3d3c56' } }} startIcon={<ContentCopyIcon />} onClick={handleCopy}>
            Copy
          </Button>
          <Button size="small" variant="contained" sx={{ backgroundColor: '#2a2a4a', color: '#ffffff', '&:hover': { backgroundColor: '#3d3c56' } }} startIcon={<DownloadIcon />} onClick={onDownload}>
            Download
          </Button>
          <Button size="small" variant="outlined" sx={{ borderColor: '#2a2a4a', color: '#ffffff', '&:hover': { borderColor: '#e94560' } }} onClick={onEditToggle}>
            {isEditing ? 'Cancel' : 'Edit'}
          </Button>
        </Box>
      </Box>

      {isEditing ? (
        <Box>
          <TextField
            fullWidth
            multiline
            rows={8}
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            variant="outlined"
            sx={{
              mb: 2,
              backgroundColor: '#0f0e17',
              borderRadius: 2,
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: '#2a2a4a'
              },
              '& .MuiInputBase-input': {
                color: '#ffffff'
              }
            }}
          />
          <Button
            variant="contained"
            sx={{ backgroundColor: '#e94560', '&:hover': { backgroundColor: '#c73652' } }}
            onClick={handleSave}
            fullWidth
          >
            Save Changes
          </Button>
        </Box>
      ) : (
        <Box
          sx={{
            padding: 2,
            backgroundColor: '#0f0e17',
            borderRadius: 2,
            border: '1px solid #2a2a4a',
            minHeight: 260,
            maxHeight: 420,
            overflowY: 'auto'
          }}
        >
          <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, color: '#e6e6f0' }}>
            {text}
          </Typography>
        </Box>
      )}
    </Paper>
  )
}
