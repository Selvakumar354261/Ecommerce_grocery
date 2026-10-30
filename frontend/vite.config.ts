import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],server:{proxy:{'/api':'http://backend:8000'}},build:{rollupOptions:{output:{manualChunks(id){if(id.includes('node_modules'))return id.includes('@mui')||id.includes('@emotion')?'material':'vendor';}}}}});

