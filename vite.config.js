import {defineConfig} from 'vite';
import {resolve} from 'node:path';
export default defineConfig({
  root:'web',publicDir:'public',
  build:{outDir:'../dist',emptyOutDir:true,rollupOptions:{input:{main:resolve('web/index.html'),admin:resolve('web/admin/index.html')}}},
  server:{port:5173,strictPort:true},preview:{port:4173,strictPort:true},
});
