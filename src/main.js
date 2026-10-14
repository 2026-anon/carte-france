import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
import { localeFr } from './locale-fr.js';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import departementsUrl from '../data/departements.geojson?url';

// Depuis MapLibre 6, le worker est un fichier à part que Vite n'embarque pas tout seul.
maplibregl.setWorkerUrl(workerUrl);

// Fond de carte sobre, gratuit et sans clé API : OpenFreeMap (données © OpenStreetMap).
const STYLE_FOND = 'https://tiles.openfreemap.org/styles/positron';

// Emprise de la France métropolitaine, Corse comprise : [[ouest, sud], [est, nord]]
// en WGS84, dans l'ordre [longitude, latitude] attendu par MapLibre.
const EMPRISE_METROPOLE = [
  [-5.5, 41.0],
  [10.0, 51.5],
];

const carte = new maplibregl.Map({
  container: 'carte',
  style: STYLE_FOND,
  bounds: EMPRISE_METROPOLE,
  fitBoundsOptions: { padding: 20 },
  locale: localeFr,
});

carte.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
carte.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');

carte.on('load', () => {
  // Les codes de départements ("01", "2A"…) sont des textes : promoteId les garde tels quels
  // comme identifiants d'entités, sans conversion en nombre.
  carte.addSource('departements', {
    type: 'geojson',
    data: departementsUrl,
    promoteId: 'code',
    attribution: 'Contours : IGN Admin Express, Licence ouverte Etalab',
  });

  // Les contours passent sous les étiquettes du fond de carte pour rester lisibles.
  const premiereCoucheTexte = carte.getStyle().layers.find((couche) => couche.type === 'symbol')?.id;

  carte.addLayer(
    {
      id: 'departements-contours',
      type: 'line',
      source: 'departements',
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': '#1d4e89',
        'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.6, 8, 1.6],
        'line-opacity': 0.85,
      },
    },
    premiereCoucheTexte,
  );
});
