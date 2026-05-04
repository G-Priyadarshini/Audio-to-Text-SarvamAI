import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }: { mode: string }) => {
  const env = loadEnv(mode, process.cwd(), '')

  const APP_PORT = Number(env.VITE_APP_PORT || 5000)
  const BASE_PATH = env.VITE_BASE_PATH || '/'
  
  return {
    plugins: [react()],
    base: BASE_PATH, 
    server: {
      port: APP_PORT,
      host: true,
    },
    build: {
      outDir: 'dist',
      sourcemap: true
    }
  }
})
