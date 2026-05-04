import React from 'react'
import { Box, FormControl, InputLabel, Select, MenuItem, CircularProgress, Typography } from '@mui/material'
import type { SelectChangeEvent } from '@mui/material'

interface LanguageSelectorProps {
  value: string
  onChange: (lang: string) => void
  disabled?: boolean
  isHealthy: boolean
}

const LANGUAGES = [
  { code: 'en-IN', label: 'English (India)' },
  { code: 'hi-IN', label: 'Hindi' },
  { code: 'ta-IN', label: 'Tamil' },
  { code: 'te-IN', label: 'Telugu' },
  { code: 'kn-IN', label: 'Kannada' },
  { code: 'ml-IN', label: 'Malayalam' },
  { code: 'mr-IN', label: 'Marathi' },
  { code: 'gu-IN', label: 'Gujarati' },
  { code: 'bn-IN', label: 'Bengali' },
  { code: 'pa-IN', label: 'Punjabi' },
  { code: 'od-IN', label: 'Odia' },
  { code: 'as-IN', label: 'Assamese' },
  { code: 'en-US', label: 'English (US)' }
]

export default function LanguageSelector({
  value,
  onChange,
  disabled = false,
  isHealthy
}: LanguageSelectorProps) {
  return (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 3, flexWrap: 'wrap' }}>
      <FormControl
        sx={{
          minWidth: 250,
          '& .MuiInputLabel-root': {
            color: '#a7a9be'
          },
          '& .MuiOutlinedInput-root': {
            backgroundColor: '#111119',
            color: '#ffffff',
            borderRadius: 2,
            '& fieldset': {
              borderColor: '#2a2a4a'
            },
            '&:hover fieldset': {
              borderColor: '#e94560'
            }
          },
          '& .MuiSelect-icon': {
            color: '#ffffff'
          }
        }}
        disabled={disabled || !isHealthy}
      >
        <InputLabel>Language</InputLabel>
        <Select
          value={value}
          onChange={(e: SelectChangeEvent<string>) => onChange(e.target.value)}
          label="Language"
          sx={{ color: '#ffffff' }}
        >
          {LANGUAGES.map(lang => (
            <MenuItem key={lang.code} value={lang.code}>
              {lang.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        {isHealthy ? (
          <>
            <Box sx={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: '#4caf50' }} />
            <Typography variant="body2" color="success">
              Online
            </Typography>
          </>
        ) : (
          <>
            <CircularProgress size={16} sx={{ color: '#e94560' }} />
            <Typography variant="body2" color="error">
              Offline
            </Typography>
          </>
        )}
      </Box>
    </Box>
  )
}
