import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
import { localeFr } from './locale-fr.js';
import { ajouterDepartements } from './departements.js';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';

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

carte.on('load', () => ajouterDepartements(carte));
