import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, '../app/static/dist'),
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/ws': {
        target: 'ws://localhost:8090',
        ws: true,
      },
      '/stream': {
        target: 'http://localhost:8090',
      },
      '/snapshot': {
        target: 'http://localhost:8090',
      },
      '/recordings': {
        target: 'http://localhost:8090',
      },
    },
  },
})
