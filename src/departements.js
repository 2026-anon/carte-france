import * as maplibregl from 'maplibre-gl';
import departementsUrl from '../data/departements.geojson?url';
import { stationsSous } from './nitrates.js';
import { railSous } from './rail.js';

const SOURCE = 'departements';
const COUCHE_FOND = 'departements-fond';
const COUCHE_CONTOURS = 'departements-contours';
const COULEUR = '#1d4e89';

// États portés par chaque département (feature-state, identifié par son code INSEE en texte).
const estSelectionne = ['boolean', ['feature-state', 'selectionne'], false];
const estSurvole = ['boolean', ['feature-state', 'survol'], false];

export function ajouterDepartements(carte) {
  // Les codes de départements ("01", "2A"…) sont des textes : promoteId les garde tels quels
  // comme identifiants d'entités, sans conversion en nombre.
  carte.addSource(SOURCE, {
    type: 'geojson',
    data: departementsUrl,
    promoteId: 'code',
    attribution: 'Contours : IGN Admin Express, Licence ouverte Etalab',
  });

  // Les couches passent sous les étiquettes du fond de carte pour rester lisibles.
  const premiereCoucheTexte = carte.getStyle().layers.find((couche) => couche.type === 'symbol')?.id;

  // Surface invisible au repos : elle sert à détecter le département touché, et à le surligner.
  carte.addLayer(
    {
      id: COUCHE_FOND,
      type: 'fill',
      source: SOURCE,
      paint: {
        'fill-color': COULEUR,
        'fill-opacity': ['case', estSelectionne, 0.35, estSurvole, 0.18, 0],
      },
    },
    premiereCoucheTexte,
  );

  carte.addLayer(
    {
      id: COUCHE_CONTOURS,
      type: 'line',
      source: SOURCE,
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': COULEUR,
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          4,
          ['case', estSelectionne, 2.4, 0.6],
          8,
          ['case', estSelectionne, 3.6, 1.6],
        ],
        'line-opacity': 0.85,
      },
    },
    premiereCoucheTexte,
  );

  activerInteraction(carte);
}

function activerInteraction(carte) {
  // Le contenu est créé une fois puis seulement mis à jour : redéfinir le contenu d'une fenêtre
  // ouverte recréerait la croix de fermeture, sans son libellé accessible.
  const elementNom = document.createElement('p');
  elementNom.className = 'departement-nom';
  const elementCode = document.createElement('p');
  elementCode.className = 'departement-code';
  const contenu = document.createElement('div');
  contenu.append(elementNom, elementCode);

  // La fermeture est gérée ici (clic ailleurs) et par la croix de la fenêtre.
  const fenetre = new maplibregl.Popup({
    className: 'fenetre-departement',
    closeOnClick: false,
    maxWidth: '280px',
    offset: 8,
  }).setDOMContent(contenu);

  let codeSelectionne = null;
  let codeSurvole = null;

  const proprietesSous = (point) => carte.queryRenderedFeatures(point, { layers: [COUCHE_FOND] })[0]?.properties;
  const definirEtat = (code, etat) => carte.setFeatureState({ source: SOURCE, id: code }, etat);

  function deselectionner() {
    if (codeSelectionne === null) return;
    definirEtat(codeSelectionne, { selectionne: false });
    codeSelectionne = null;
  }

  function survoler(code) {
    if (code === codeSurvole) return;
    if (codeSurvole !== null) definirEtat(codeSurvole, { survol: false });
    if (code !== null) definirEtat(code, { survol: true });
    codeSurvole = code;
  }

  // Quelle que soit la façon dont la fenêtre se ferme (croix ou clic ailleurs), la sélection disparaît.
  fenetre.on('close', deselectionner);

  // « click » couvre aussi le toucher : MapLibre le déclenche pour un simple appui, pas pour un glissement.
  carte.on('click', (e) => {
    // Un point de mesure sous le doigt prime : sa fenêtre s'ouvre (src/nitrates.js), la sélection du département disparaît.
    // Il en va de même d'une gare ou d'une ligne du réseau ferré affiché (src/rail.js).
    if (stationsSous(carte, e.point).length > 0 || railSous(carte, e.point).length > 0) {
      fenetre.remove();
      return;
    }
    const departement = proprietesSous(e.point);
    if (!departement) {
      fenetre.remove();
      return;
    }

    if (departement.code !== codeSelectionne) {
      deselectionner();
      definirEtat(departement.code, { selectionne: true });
      codeSelectionne = departement.code;
    }

    elementNom.textContent = departement.nom;
    elementCode.textContent = `Code INSEE : ${departement.code}`;
    fenetre.setLngLat(e.lngLat);
    if (!fenetre.isOpen()) fenetre.addTo(carte);
  });

  // Le survol n'existe qu'avec une souris : sur écran tactile, il resterait bloqué après un appui.
  if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    carte.on('mousemove', (e) => {
      const code = proprietesSous(e.point)?.code ?? null;
      carte.getCanvas().style.cursor = code === null ? '' : 'pointer';
      survoler(code);
    });
    carte.on('mouseout', () => {
      carte.getCanvas().style.cursor = '';
      survoler(null);
    });
  }
}
