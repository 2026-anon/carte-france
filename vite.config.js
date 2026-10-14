import { defineConfig } from 'vite';

// base relative : le dossier dist/ peut être servi depuis n'importe quel sous-chemin
// (GitHub Pages, hébergement statique, etc.).
export default defineConfig({
  base: './',
  build: {
    // MapLibre GL JS pèse à lui seul ~1 Mo : on évite l'avertissement de taille de chunk.
    chunkSizeWarningLimit: 1200,
  },
});
