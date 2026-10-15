import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
import { localeFr } from './locale-fr.js';
import { ajouterDepartements } from './departements.js';
import { ajouterNitrates } from './nitrates.js';
import { ajouterFiltres } from './filtres.js';
import { ajouterCouches } from './couches.js';
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

// Noms en français pour les pays et les villes du fond de carte, avec repli sur le nom local
// si une étiquette n'a pas de champ « name:fr » dans les tuiles.
carte.on('style.load', () => {
  for (const couche of carte.getStyle().layers) {
    if (couche.type === 'symbol' && couche['source-layer'] === 'place') {
      carte.setLayoutProperty(couche.id, 'text-field', ['coalesce', ['get', 'name:fr'], ['get', 'name']]);
    }
  }
});

// Le panneau (couches, filtres, légende) reste au-dessus des crédits, dont la hauteur varie avec la largeur de l'écran
// et avec la longueur des mentions : on la mesure plutôt que de la deviner (voir .panneau dans style.css).
const credits = carte.getContainer().querySelector('.maplibregl-ctrl-attrib');
new ResizeObserver(() => {
  const hauteur = carte.getContainer().getBoundingClientRect().bottom - credits.getBoundingClientRect().top;
  document.documentElement.style.setProperty('--bas-panneau', `${Math.ceil(hauteur) + 8}px`);
}).observe(credits);

carte.on('load', async () => {
  ajouterDepartements(carte);
  const couches = await ajouterNitrates(carte);
  const filtres = ajouterFiltres(carte, couches);
  ajouterCouches(carte, couches, filtres.majCompteurs);
});
