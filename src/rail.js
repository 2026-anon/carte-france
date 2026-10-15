import * as maplibregl from 'maplibre-gl';
import { creer } from './dom.js';
import { COUCHES, PETIT_ECRAN, stationsSous } from './nitrates.js';
import urlLignes from '../data/rfn_lignes.geojson?url';
import urlGares from '../data/rfn_gares.geojson?url';
import urlMeta from '../data/rfn_meta.json?url';

// Couche « Réseau ferré national » : deux sous-couches, les lignes et les gares, affichables séparément. Les données viennent
// de scripts/preparer_rfn.py (SNCF Réseau, ODbL). Elles ne sont chargées qu'à la première activation d'une sous-couche : la
// carte au démarrage est celle d'avant.

// SEULE définition des couleurs des lignes (légende officielle « Le réseau ferré en France ») : le dessin, la légende et les filtres la lisent.
export const COULEURS = {
  lgv: '#00A0E3',
  lgvAutre: '#00A9AC', // LGV gérée par un autre gestionnaire (relevé manuel, voir scripts/preparer_rfn.py)
  suspendueAutre: '#00A9AC', // ligne suspendue, reprise programmée par un autre gestionnaire
  autre: '#DC8E62', // autre réseau ou exploitation touristique
  mixte: '#5D4FA1',
  fret: '#65BC45',
  metrique: '#ED1650',
  evit: '#5D4FA1', // évitements : violet, comme les lignes mixtes
  fermee: '#57585A',
  suspendue: '#76787A',
};

// Sous-couches : id de la source, libellé du bloc des couches.
export const SOUS_COUCHES_RAIL = [
  { id: 'rfn_lignes', nom: 'Lignes', attribution: 'Réseau ferré : SNCF Réseau (data.sncf.com), ODbL' },
  { id: 'rfn_gares', nom: 'Gares', attribution: 'Gares : SNCF Réseau et Gares & Connexions (data.sncf.com), ODbL' },
];

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const mois = (aaaammjj) => `${MOIS[Number(aaaammjj.slice(5, 7)) - 1]} ${aaaammjj.slice(0, 4)}`;

// Couche des contours des départements (src/departements.js) et opacité qu'elle prend quand le réseau ferré est affiché.
const CONTOURS_DEPARTEMENTS = 'departements-contours';
const OPACITE_CONTOURS_ATTENUEE = 0.3;

const POLICES = { gras: ['Noto Sans Bold'], normal: ['Noto Sans Regular'], italique: ['Noto Sans Italic'] };
const VIOLET = COULEURS.mixte;

// Largeurs et écarts en pixels, par niveau de zoom.
const largeur = (z4, z7, z10, z14) => ['interpolate', ['linear'], ['zoom'], 4, z4, 7, z7, 10, z10, 14, z14];

const estExploitee = ['==', ['get', 'g'], 'E'];
const categorieEn = (...categories) => ['in', ['get', 'c'], ['literal', categories]];
const traitsVoies = categorieEn('mixte', 'fret', 'metrique', 'evit');

// Couleur d'un trait exploité selon sa catégorie.
const couleurCategorie = ['to-color', ['match', ['get', 'c'], 'lgv', COULEURS.lgv, 'lgv_autre', COULEURS.lgvAutre, 'mixte', COULEURS.mixte, 'fret', COULEURS.fret,
  'metrique', COULEURS.metrique, 'evit', COULEURS.evit, COULEURS.mixte]];

// Décalage des traits parallèles : 2 traits à ±1,4 px, 3 traits à -2,7, 0 et +2,7 px (valeurs au zoom 10).
const ecart = (coefficient) => {
  const pour = (zoom) => ['case', ['==', ['get', 'v'], 2], coefficient * zoom[0], coefficient * zoom[1]];
  return ['interpolate', ['linear'], ['zoom'], 4, pour([0.6, 1.2]), 7, pour([0.9, 1.8]), 10, pour([1.4, 2.7]), 14, pour([2.2, 4.2])];
};

// Couches de lignes, de la plus basse à la plus haute. `filtre` est le filtre de base de la couche ; le filtre de l'utilisateur
// (catégories, électrification, voies) s'y ajoute (voir appliquer).
const LIGNES = [
  {
    id: 'rfn_lignes_fermees', // ligne non exploitée : pointillé fin
    filtre: ['==', ['get', 'g'], 'F'],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': COULEURS.fermee, 'line-width': largeur(0.5, 0.8, 1.2, 1.8), 'line-dasharray': [1, 2] },
  },
  {
    id: 'rfn_lignes_suspendues', // ligne suspendue : longs tirets
    filtre: ['==', ['get', 'g'], 'N'],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': COULEURS.suspendue, 'line-width': largeur(0.6, 1, 1.5, 2.2), 'line-dasharray': [6, 3] },
  },
  {
    id: 'rfn_lignes_suspendues_autre', // ligne suspendue reprise par un autre gestionnaire : longs tirets, couleur de ce gestionnaire
    filtre: ['==', ['get', 'g'], 'R'],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': COULEURS.suspendueAutre, 'line-width': largeur(0.8, 1.3, 1.8, 2.6), 'line-dasharray': [10, 4] },
  },
  {
    id: 'rfn_autre', // autre réseau ou exploitation touristique : trait fin (les petits traits sont dans rfn_autre_traits)
    filtre: ['==', ['get', 'g'], 'A'],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': COULEURS.autre, 'line-width': largeur(0.6, 1, 1.4, 2) },
  },
  {
    id: 'rfn_lgv', // LGV (RFN ou autre gestionnaire) : très épais, trait coloré
    filtre: ['all', estExploitee, categorieEn('lgv', 'lgv_autre')],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': couleurCategorie, 'line-width': largeur(1.8, 3, 5, 8) },
  },
  {
    id: 'rfn_lgv_filet', // LGV : filet blanc au centre (double trait)
    filtre: ['all', estExploitee, categorieEn('lgv', 'lgv_autre')],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': '#ffffff', 'line-width': largeur(0.5, 0.8, 1.3, 2) },
  },
  {
    id: 'rfn_voies_centre', // voie unique et voies multiples : trait central
    filtre: ['all', estExploitee, traitsVoies, ['!=', ['get', 'v'], 2]],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': couleurCategorie, 'line-width': largeur(0.6, 1, 1.4, 2) },
  },
  {
    id: 'rfn_voies_gauche', // double voie et voies multiples : traits latéraux
    filtre: ['all', estExploitee, traitsVoies, ['>=', ['get', 'v'], 2]],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': couleurCategorie, 'line-width': largeur(0.6, 1, 1.4, 2), 'line-offset': ecart(-1) },
  },
  {
    id: 'rfn_voies_droite',
    filtre: ['all', estExploitee, traitsVoies, ['>=', ['get', 'v'], 2]],
    layout: { 'line-cap': 'butt' },
    paint: { 'line-color': couleurCategorie, 'line-width': largeur(0.6, 1, 1.4, 2), 'line-offset': ecart(1) },
  },
];

// Traits perpendiculaires réguliers des lignes électrifiées : un motif par couleur, visible à partir du zoom 7.
const ELECTRIFICATION = ['mixte', 'fret', 'metrique'].map((categorie) => ({
  id: `rfn_electrifie_${categorie}`,
  image: `rfn-trait-${categorie}`,
  couleur: COULEURS[categorie],
  filtre: ['all', estExploitee, categorieEn(categorie), ['==', ['get', 'e'], 1]],
}));

// Petits traits de l'« autre réseau ou exploitation touristique » : même motif que l'électrification, sur un trait fin de cette couleur.
const TRAITS_AUTRE = { id: 'rfn_autre_traits', image: 'rfn-trait-autre', couleur: COULEURS.autre, filtre: ['==', ['get', 'g'], 'A'] };

function creerImageTrait(couleur) {
  const canvas = document.createElement('canvas');
  canvas.width = 32;
  canvas.height = 8;
  const contexte = canvas.getContext('2d');
  contexte.fillStyle = couleur;
  contexte.fillRect(15, 0, 2, 8); // un trait perpendiculaire par motif ; pixelRatio 2 : période de 16 px à l'écran
  return contexte.getImageData(0, 0, 32, 8);
}

// Niveaux d'intérêt des gares : id, libellé, zoom d'apparition, style du nom. Les nationales s'affichent d'abord.
export const NIVEAUX = [
  { code: 'N', nom: 'National', libelle: "Gare desservie d'intérêt national", zoom: 4.5, majuscules: true, police: 'gras', taille: [5, 11, 9, 14, 12, 17] },
  { code: 'R', nom: 'Régional', libelle: "Gare desservie d'intérêt régional", zoom: 7, majuscules: false, police: 'gras', taille: [7, 10, 10, 12, 13, 14] },
  { code: 'L', nom: 'Local', libelle: "Gare desservie d'intérêt local", zoom: 9.5, majuscules: false, police: 'normal', taille: [9, 9, 11, 10, 14, 12] },
];
const NON_DESSERVIE = { code: '', libelle: 'Gare non desservie voyageurs, pouvant être desservie fret', zoom: 9.5, police: 'italique', taille: [9, 9, 11, 10, 14, 12] };

const filtreNiveau = (niveau) => (niveau.code ? ['all', ['==', ['get', 'd'], 1], ['==', ['get', 'i'], niveau.code]] : ['==', ['get', 'd'], 0]);

// Couches de gares : un repère sur la voie et un nom par niveau, de la plus basse (non desservies) à la plus haute (nationales),
// car en cas de collision l'étiquette de la couche la plus haute passe en premier.
function couchesGares() {
  const couches = [];
  for (const niveau of [NON_DESSERVIE, ...[...NIVEAUX].reverse()]) {
    const cle = niveau.code || 'x';
    const couleur = niveau.code ? '#222222' : VIOLET;
    couches.push({
      id: `rfn_gares_reperes_${cle}`,
      type: 'circle',
      minzoom: niveau.zoom,
      filtre: filtreNiveau(niveau),
      paint: {
        'circle-radius': largeur(1.5, 2, 3, 5),
        'circle-color': '#ffffff',
        'circle-stroke-color': couleur,
        'circle-stroke-width': 1.2,
      },
    });
    const [z1, t1, z2, t2, z3, t3] = niveau.taille;
    couches.push({
      id: `rfn_gares_noms_${cle}`,
      type: 'symbol',
      minzoom: niveau.zoom,
      filtre: filtreNiveau(niveau),
      layout: {
        'text-field': ['get', 'n'],
        'text-font': POLICES[niveau.police],
        'text-size': ['interpolate', ['linear'], ['zoom'], z1, t1, z2, t2, z3, t3],
        'text-transform': niveau.majuscules ? 'uppercase' : 'none',
        'text-anchor': 'left',
        'text-offset': [0.7, 0],
        'text-max-width': 9,
      },
      paint: { 'text-color': couleur, 'text-halo-color': '#ffffff', 'text-halo-width': 1.4 },
    });
  }
  return couches;
}

const arrondi = (n) => Math.round(n).toLocaleString('fr-FR');

// Longueur d'un tracé en kilomètres (distance sur la sphère, tracé simplifié).
function longueurKm(coordonnees) {
  let total = 0;
  for (let i = 1; i < coordonnees.length; i++) {
    const [x1, y1] = coordonnees[i - 1];
    const [x2, y2] = coordonnees[i];
    const dx = (x2 - x1) * Math.cos(((y1 + y2) / 2) * (Math.PI / 180)) * 111.32;
    total += Math.hypot(dx, (y2 - y1) * 110.57);
  }
  return total;
}

// Symbole d'une ligne dans la légende : un petit dessin SVG qui reprend le style de la carte.
function symboleLigne({ couleur, voies = 1, electrifie = false, epais = false, tirets = null, court = false }) {
  const ns = 'http://www.w3.org/2000/svg';
  const largeurSvg = court ? 18 : 30;
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('class', 'rail-symbole');
  svg.setAttribute('width', String(largeurSvg));
  svg.setAttribute('height', '14');
  svg.setAttribute('viewBox', `0 0 ${largeurSvg} 14`);
  svg.setAttribute('aria-hidden', 'true');
  const trait = (y, epaisseur, c, pointilles) => {
    const l = document.createElementNS(ns, 'line');
    l.setAttribute('x1', '1');
    l.setAttribute('x2', String(largeurSvg - 1));
    l.setAttribute('y1', String(y));
    l.setAttribute('y2', String(y));
    l.setAttribute('stroke', c);
    l.setAttribute('stroke-width', String(epaisseur));
    if (pointilles) l.setAttribute('stroke-dasharray', pointilles);
    svg.append(l);
  };
  if (electrifie) {
    for (let x = 3; x < largeurSvg - 1; x += 5) {
      const t = document.createElementNS(ns, 'line');
      t.setAttribute('x1', String(x));
      t.setAttribute('x2', String(x));
      t.setAttribute('y1', '2');
      t.setAttribute('y2', '12');
      t.setAttribute('stroke', couleur);
      t.setAttribute('stroke-width', '1');
      svg.append(t);
    }
  }
  if (epais) {
    trait(7, 6, couleur);
    trait(7, 1.5, '#ffffff');
  } else if (tirets) {
    trait(7, 1.8, couleur, tirets);
  } else {
    const ys = { 1: [7], 2: [5.4, 8.6], 3: [4, 7, 10] }[voies];
    for (const y of ys) trait(y, 1.4, couleur);
  }
  return svg;
}

const ligneLegende = (symboles, texte) => {
  const item = creer('li', 'rail-legende-ligne');
  const groupe = creer('span', 'rail-symboles');
  groupe.append(...symboles);
  item.append(creer('span', 'rail-libelle', texte), groupe);
  return item;
};

function remplirLegende(meta) {
  const titre = creer('summary', 'bloc-titre', 'Réseau ferré national');
  const lignes = creer('ul', 'rail-liste');
  lignes.append(
    ligneLegende([symboleLigne({ couleur: COULEURS.lgv, epais: true })], 'Ligne à grande vitesse'),
    ligneLegende([symboleLigne({ couleur: COULEURS.lgvAutre, epais: true })], 'LGV gérée par un autre gestionnaire'),
    ligneLegende([1, 2, 3].map((voies) => symboleLigne({ couleur: COULEURS.mixte, voies })), 'Ligne mixte'),
    ligneLegende([1, 2, 3].map((voies) => symboleLigne({ couleur: COULEURS.fret, voies })), 'Ligne fret'),
    ligneLegende([symboleLigne({ couleur: COULEURS.metrique })], 'Voie métrique (autre réseau ou touristique)'),
    ligneLegende([symboleLigne({ couleur: COULEURS.fermee, tirets: '1.5 3' })], 'Ligne non exploitée'),
    ligneLegende([symboleLigne({ couleur: COULEURS.suspendue, tirets: '7 3' })], 'Ligne suspendue, reprise programmée ou possible'),
    ligneLegende([symboleLigne({ couleur: COULEURS.suspendueAutre, tirets: '11 4' })], 'Ligne suspendue, reprise programmée par un autre gestionnaire'),
    ligneLegende([symboleLigne({ couleur: COULEURS.autre, electrifie: true })], 'Autre réseau ou exploitation touristique'),
    ligneLegende([symboleLigne({ couleur: COULEURS.evit, court: true })], 'Évitement'),
  );
  const explication = creer('ul', 'rail-liste');
  explication.append(
    ligneLegende([1, 2, 3].map((voies) => symboleLigne({ couleur: '#555555', voies })), '1, 2, 3 traits : voie unique, double voie, voies multiples'),
    ligneLegende([symboleLigne({ couleur: COULEURS.mixte, electrifie: true })], 'Traits perpendiculaires : ligne électrifiée'),
  );
  const gares = creer('ul', 'rail-liste');
  for (const niveau of [...NIVEAUX, NON_DESSERVIE]) {
    const item = creer('li');
    const nom = creer('span', `rail-gare rail-gare-${niveau.code || 'x'}`, niveau.code === 'N' ? 'GARE' : 'Gare');
    item.append(nom, ' ', niveau.libelle.replace(/^Gare /, '').replace(/^desservie /, 'desservie '));
    gares.append(item);
  }
  const dates = Object.values(meta.sources).map((source) => source.donnees_du).sort();
  const note = creer('p', 'legende-note',
    `Source : SNCF Réseau et SNCF Gares & Connexions (ODbL), données de ${mois(dates[0])} à ${mois(dates[dates.length - 1])} selon le jeu. `
    + 'LGV d’un autre gestionnaire, lignes suspendues reprises par un autre gestionnaire, autre réseau et exploitation touristique : '
    + 'aucun jeu ouvert ne les décrit, seuls les tronçons relevés à la main sur la carte SNCF Réseau (mars 2026) sont dessinés, '
    + 'après vérification du code de ligne et des gares ; les autres restent classés selon le statut des données ouvertes.');
  const bloc = document.getElementById('legende-rail');
  bloc.replaceChildren(titre, creer('p', 'legende-sous-titre', 'Lignes'), lignes, explication, creer('p', 'legende-sous-titre', 'Gares'), gares, note);
  bloc.open = !window.matchMedia(PETIT_ECRAN).matches;
}

// Valeurs des cases de catégorie : `c` des lignes exploitées, plus 'inactif' (g N ou F), 'suspendue_autre' (g R) et 'autre' (g A).
const TOUTES_CATEGORIES = ['lgv', 'lgv_autre', 'mixte', 'fret', 'metrique', 'inactif', 'suspendue_autre', 'autre'];
const GROUPE_DE_CATEGORIE = { inactif: ['N', 'F'], suspendue_autre: ['R'], autre: ['A'] };

const MARGE_TOUCHER = 10;
const MARGE_SOURIS = 4;

// Sous-couches affichées (mises à jour par ajouterRail) : railSous n'interroge que leurs couches.
const sousCouchesVisibles = new Set();
const COUCHES_CLIQUABLES = {
  rfn_gares: [NON_DESSERVIE, ...NIVEAUX].map((niveau) => `rfn_gares_reperes_${niveau.code || 'x'}`),
  rfn_lignes: LIGNES.map(({ id }) => id),
};

// Éléments du réseau ferré sous un appui ou un clic : d'abord les gares, puis les lignes, dans les sous-couches visibles.
export function railSous(carte, point) {
  const marge = window.matchMedia('(pointer: coarse)').matches ? MARGE_TOUCHER : MARGE_SOURIS;
  const zone = [[point.x - marge, point.y - marge], [point.x + marge, point.y + marge]];
  for (const sousCouche of ['rfn_gares', 'rfn_lignes']) {
    if (!sousCouchesVisibles.has(sousCouche)) continue;
    const couches = COUCHES_CLIQUABLES[sousCouche].filter((id) => carte.getLayer(id));
    if (couches.length === 0) continue;
    const trouves = carte.queryRenderedFeatures(zone, { layers: couches });
    if (trouves.length > 0) return trouves;
  }
  return [];
}

const TEXTE_CATEGORIE = { lgv: 'Ligne à grande vitesse', lgv_autre: 'LGV gérée par un autre gestionnaire', mixte: 'Ligne mixte', fret: 'Ligne fret', metrique: 'Ligne à voie métrique', evit: 'Évitement' };
const TEXTE_VOIES = { 1: 'voie unique', 2: 'double voie', 3: 'voies multiples' };
const TEXTE_NIVEAU = { N: "d'intérêt national", R: "d'intérêt régional", L: "d'intérêt local" };

function activerInteraction(carte) {
  const type = creer('p', 'station-type', 'Réseau ferré national');
  const titre = creer('p', 'station-nom');
  const ligne1 = creer('p', 'station-detail');
  const ligne2 = creer('p', 'station-detail');
  const ligne3 = creer('p', 'station-detail');
  const contenu = creer('div');
  contenu.append(type, titre, ligne1, ligne2, ligne3);
  const fenetre = new maplibregl.Popup({ className: 'fenetre-station', closeOnClick: false, maxWidth: '300px', offset: 10 }).setDOMContent(contenu);

  carte.on('click', (e) => {
    // Un point de mesure des nitrates sous le doigt prime : sa fenêtre s'ouvre (src/nitrates.js).
    const element = stationsSous(carte, e.point).length > 0 ? null : railSous(carte, e.point)[0];
    if (!element) {
      fenetre.remove();
      return;
    }
    const p = element.properties;
    if (element.layer.id.startsWith('rfn_gares')) {
      titre.textContent = p.n;
      ligne1.textContent = p.d ? `Gare desservie ${TEXTE_NIVEAU[p.i]}` : 'Gare non desservie voyageurs, pouvant être desservie fret';
      ligne2.textContent = `${p.c || 'Commune inconnue'} · code UIC ${p.u}`;
      ligne3.textContent = p.s === 'defaut' ? 'Niveau d’intérêt non disponible : local par défaut.' : (p.d ? `Segment DRG : ${p.s === 'drg' ? 'Gares de voyageurs' : 'Fréquentation en gares'}` : '');
    } else {
      const g = p.g;
      titre.textContent = `Ligne ${p.l}`;
      if (g === 'E') {
        const voies = TEXTE_VOIES[p.v];
        ligne1.textContent = `${TEXTE_CATEGORIE[p.c]}, exploitée`;
        ligne2.textContent = p.c === 'lgv' || p.c === 'lgv_autre' || p.c === 'evit' ? '' : `${voies}, ${p.e ? 'électrifiée' : 'non électrifiée'}`;
      } else {
        ligne1.textContent = { N: 'Ligne suspendue (neutralisée)', R: 'Ligne suspendue, reprise programmée par un autre gestionnaire',
          A: 'Autre réseau ou exploitation touristique' }[g] || 'Ligne non exploitée (fermée)';
        ligne2.textContent = g === 'R' || g === 'A' ? 'Classement d’après un relevé manuel (carte SNCF Réseau, mars 2026)' : '';
      }
      ligne3.textContent = '';
    }
    for (const l of [ligne1, ligne2, ligne3]) l.hidden = l.textContent === '';
    fenetre.setLngLat(e.lngLat);
    if (!fenetre.isOpen()) fenetre.addTo(carte);
  });

  if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    carte.on('mousemove', (e) => {
      if (railSous(carte, e.point).length > 0) carte.getCanvas().style.cursor = 'pointer';
    });
  }
}

// Ajoute le réseau ferré : renvoie { sousCouches, afficher(id, visible), quandChange } pour le bloc des couches. Rien n'est chargé
// avant la première activation d'une sous-couche.
export function ajouterRail(carte) {
  const etat = {
    visible: { rfn_lignes: false, rfn_gares: false },
    donnees: { rfn_lignes: null, rfn_gares: null },
    categories: new Set(TOUTES_CATEGORIES),
    electrifie: new Set([0, 1]),
    voies: new Set([1, 2, 3]),
    niveaux: new Set(['N', 'R', 'L']),
    gares: new Set(['desservie', 'non']),
  };
  let meta = null;
  let interactionActive = false;
  let opaciteContours = null;
  const filtres = creer('details', 'bloc filtres');
  filtres.id = 'filtres-rail';
  filtres.hidden = true;
  const legende = document.getElementById('legende-rail');
  document.querySelector('.panneau').insertBefore(filtres, document.getElementById('legende'));

  // Filtre des lignes : catégorie, électrification et nombre de voies s'appliquent aux lignes exploitées ; les lignes
  // non exploitées ou suspendues dépendent de la seule case « Non exploitée ou suspendue ».
  function filtreLignes() {
    const categories = [...etat.categories].filter((c) => !GROUPE_DE_CATEGORIE[c]);
    const groupes = [...etat.categories].flatMap((c) => GROUPE_DE_CATEGORIE[c] || []);
    if (etat.categories.has('mixte')) categories.push('evit');
    return ['any',
      ['all', estExploitee, ['in', ['get', 'c'], ['literal', categories]], ['in', ['get', 'e'], ['literal', [...etat.electrifie]]],
        ['in', ['get', 'v'], ['literal', [...etat.voies]]]],
      ['in', ['get', 'g'], ['literal', groupes]],
    ];
  }

  function filtreGares(niveau) {
    const voulu = niveau.code ? etat.niveaux.has(niveau.code) && etat.gares.has('desservie') : etat.gares.has('non');
    return voulu ? filtreNiveau(niveau) : ['literal', false];
  }

  function appliquer() {
    if (carte.getLayer('rfn_lgv')) {
      const filtre = filtreLignes();
      for (const { id, filtre: base } of [...LIGNES, ...ELECTRIFICATION, TRAITS_AUTRE]) carte.setFilter(id, ['all', base, filtre]);
    }
    if (carte.getLayer('rfn_gares_reperes_N')) {
      for (const niveau of [NON_DESSERVIE, ...NIVEAUX]) {
        const f = filtreGares(niveau);
        const cle = niveau.code || 'x';
        carte.setFilter(`rfn_gares_reperes_${cle}`, f);
        carte.setFilter(`rfn_gares_noms_${cle}`, f);
      }
    }
    majFiltres();
  }

  // Une case à cocher par valeur : `ensemble` contient les valeurs cochées.
  function groupeCases(intitule, valeurs, ensemble) {
    const groupe = creer('fieldset', 'case-groupe');
    groupe.append(creer('legend', 'case-intitule', intitule));
    for (const { valeur, libelle, symbole } of valeurs) {
      const caseACocher = creer('input');
      caseACocher.type = 'checkbox';
      caseACocher.checked = ensemble.has(valeur);
      caseACocher.addEventListener('change', () => {
        if (caseACocher.checked) ensemble.add(valeur);
        else ensemble.delete(valeur);
        appliquer();
      });
      const ligne = creer('label', 'case-ligne');
      ligne.append(caseACocher);
      if (symbole) ligne.append(symbole);
      ligne.append(libelle);
      groupe.append(ligne);
    }
    return groupe;
  }

  const compteurLignes = creer('p', 'filtres-compteur');
  const compteurGares = creer('p', 'filtres-compteur');
  function majFiltres() {
    if (etat.donnees.rfn_lignes) {
      let affiches = 0;
      let total = 0;
      for (const f of etat.donnees.rfn_lignes.features) {
        total += f.km;
        const p = f.properties;
        const garde = p.g === 'E'
          ? (p.c === 'evit' ? etat.categories.has('mixte') : etat.categories.has(p.c)) && etat.electrifie.has(p.e) && etat.voies.has(p.v)
          : GROUPE_DE_CATEGORIE.inactif.includes(p.g) ? etat.categories.has('inactif')
            : etat.categories.has(p.g === 'R' ? 'suspendue_autre' : 'autre');
        if (garde) affiches += f.km;
      }
      compteurLignes.textContent = `Lignes : ≈ ${arrondi(affiches)} km affichés sur ≈ ${arrondi(total)} km`;
    }
    if (etat.donnees.rfn_gares) {
      const gares = etat.donnees.rfn_gares.features;
      const affichees = gares.filter((f) => {
        const p = f.properties;
        return p.d ? etat.niveaux.has(p.i) && etat.gares.has('desservie') : etat.gares.has('non');
      }).length;
      compteurGares.textContent = `Gares : ${arrondi(affichees)} affichées sur ${arrondi(gares.length)} (selon le zoom)`;
    }
    compteurLignes.hidden = !(etat.visible.rfn_lignes && etat.donnees.rfn_lignes);
    compteurGares.hidden = !(etat.visible.rfn_gares && etat.donnees.rfn_gares);
  }

  function construireFiltres() {
    const titre = creer('summary', 'bloc-titre', 'Filtres du réseau ferré');
    const parties = [titre];
    if (etat.visible.rfn_lignes) {
      parties.push(
        groupeCases('Lignes : catégorie', [
          { valeur: 'lgv', libelle: 'Ligne à grande vitesse', symbole: symboleLigne({ couleur: COULEURS.lgv, epais: true, court: true }) },
          { valeur: 'lgv_autre', libelle: 'LGV, autre gestionnaire', symbole: symboleLigne({ couleur: COULEURS.lgvAutre, epais: true, court: true }) },
          { valeur: 'mixte', libelle: 'Mixte', symbole: symboleLigne({ couleur: COULEURS.mixte, court: true }) },
          { valeur: 'fret', libelle: 'Fret', symbole: symboleLigne({ couleur: COULEURS.fret, court: true }) },
          { valeur: 'metrique', libelle: 'Voie métrique', symbole: symboleLigne({ couleur: COULEURS.metrique, court: true }) },
          { valeur: 'inactif', libelle: 'Non exploitée ou suspendue', symbole: symboleLigne({ couleur: COULEURS.suspendue, tirets: '4 2', court: true }) },
          { valeur: 'suspendue_autre', libelle: 'Suspendue, autre gestionnaire', symbole: symboleLigne({ couleur: COULEURS.suspendueAutre, tirets: '6 2', court: true }) },
          { valeur: 'autre', libelle: 'Autre réseau ou touristique', symbole: symboleLigne({ couleur: COULEURS.autre, court: true }) },
        ], etat.categories),
        groupeCases('Électrification', [{ valeur: 1, libelle: 'Électrifiée' }, { valeur: 0, libelle: 'Non électrifiée' }], etat.electrifie),
        groupeCases('Nombre de voies', [{ valeur: 1, libelle: 'Voie unique' }, { valeur: 2, libelle: 'Double voie' }, { valeur: 3, libelle: 'Voies multiples' }], etat.voies),
      );
    }
    if (etat.visible.rfn_gares) {
      parties.push(
        groupeCases("Gares : niveau d'intérêt", NIVEAUX.map((n) => ({ valeur: n.code, libelle: n.nom })), etat.niveaux),
        groupeCases('Desserte voyageurs', [{ valeur: 'desservie', libelle: 'Desservie' }, { valeur: 'non', libelle: 'Non desservie (fret)' }], etat.gares),
      );
    }
    const zoneCompteurs = creer('div', 'filtres-compteurs');
    zoneCompteurs.setAttribute('role', 'status');
    zoneCompteurs.append(compteurLignes, compteurGares);
    const reinitialiser = creer('button', 'filtres-reinit', 'Réinitialiser');
    reinitialiser.type = 'button';
    reinitialiser.addEventListener('click', () => {
      etat.categories = new Set(TOUTES_CATEGORIES);
      etat.electrifie = new Set([0, 1]);
      etat.voies = new Set([1, 2, 3]);
      etat.niveaux = new Set(['N', 'R', 'L']);
      etat.gares = new Set(['desservie', 'non']);
      construireFiltres();
      appliquer();
    });
    filtres.replaceChildren(...parties, zoneCompteurs, reinitialiser);
    filtres.open = !window.matchMedia(PETIT_ECRAN).matches;
    majFiltres();
  }

  const premiereCoucheTexte = () => carte.getStyle().layers.find((couche) => couche.type === 'symbol')?.id;
  // Les lignes passent sous les points de nitrates (qui restent lisibles) ; les gares, au-dessus d'eux mais sous les étiquettes du fond.
  const sousLesPoints = () => (carte.getLayer(COUCHES[0].id) ? COUCHES[0].id : premiereCoucheTexte());

  function ajouterLignes() {
    const config = SOUS_COUCHES_RAIL[0];
    carte.addSource(config.id, { type: 'geojson', data: etat.donnees.rfn_lignes, attribution: config.attribution });
    for (const { image, couleur } of [...ELECTRIFICATION, TRAITS_AUTRE]) carte.addImage(image, creerImageTrait(couleur), { pixelRatio: 2 });
    for (const { id, filtre, layout, paint } of LIGNES) {
      carte.addLayer({ id, type: 'line', source: config.id, filter: filtre, layout, paint }, sousLesPoints());
    }
    for (const { id, image, filtre } of [...ELECTRIFICATION, TRAITS_AUTRE]) {
      carte.addLayer({
        id, type: 'line', source: config.id, minzoom: 7, filter: filtre,
        paint: { 'line-pattern': image, 'line-width': ['interpolate', ['linear'], ['zoom'], 7, 4, 10, 6, 14, 9] },
      }, sousLesPoints());
    }
  }

  function ajouterGares() {
    const config = SOUS_COUCHES_RAIL[1];
    carte.addSource(config.id, { type: 'geojson', data: etat.donnees.rfn_gares, attribution: config.attribution });
    for (const { filtre, ...couche } of couchesGares()) {
      carte.addLayer({ ...couche, source: config.id, filter: filtre }, premiereCoucheTexte());
    }
  }

  const prefixes = { rfn_lignes: (id) => id.startsWith('rfn_') && !id.startsWith('rfn_gares'), rfn_gares: (id) => id.startsWith('rfn_gares') };

  function majVisibilite() {
    for (const [sous, estDeLaSousCouche] of Object.entries(prefixes)) {
      for (const couche of carte.getStyle().layers) {
        if (estDeLaSousCouche(couche.id)) carte.setLayoutProperty(couche.id, 'visibility', etat.visible[sous] ? 'visible' : 'none');
      }
    }
    for (const [sous, visible] of Object.entries(etat.visible)) {
      if (visible) sousCouchesVisibles.add(sous);
      else sousCouchesVisibles.delete(sous);
    }
    const rien = !etat.visible.rfn_lignes && !etat.visible.rfn_gares;
    // Les contours des départements, aussi marqués que les lignes, s'y confondraient : ils s'atténuent tant que le réseau est affiché.
    if (carte.getLayer(CONTOURS_DEPARTEMENTS)) {
      opaciteContours ??= carte.getPaintProperty(CONTOURS_DEPARTEMENTS, 'line-opacity');
      carte.setPaintProperty(CONTOURS_DEPARTEMENTS, 'line-opacity', rien ? opaciteContours : OPACITE_CONTOURS_ATTENUEE);
    }
    filtres.hidden = rien;
    legende.hidden = rien;
    if (!rien) construireFiltres();
  }

  const chargements = {};
  const charger = (id) => (chargements[id] ??= chargerDonnees(id).catch((erreur) => {
    delete chargements[id]; // un échec réseau n'est pas mémorisé : un nouvel essai est possible
    throw erreur;
  }));

  async function chargerDonnees(id) {
    if (!meta) meta = await (await fetch(urlMeta)).json();
    const donnees = await (await fetch(id === 'rfn_lignes' ? urlLignes : urlGares)).json();
    if (id === 'rfn_lignes') for (const f of donnees.features) f.km = longueurKm(f.geometry.coordinates);
    etat.donnees[id] = donnees;
    if (id === 'rfn_lignes') ajouterLignes();
    else ajouterGares();
    if (!interactionActive) {
      activerInteraction(carte);
      interactionActive = true;
    }
    remplirLegende(meta);
  }

  return {
    sousCouches: SOUS_COUCHES_RAIL,
    // Affiche ou masque une sous-couche ; la première fois, charge ses données (la promesse se termine à l'affichage).
    async afficher(id, visible) {
      etat.visible[id] = visible;
      if (visible) await charger(id);
      majVisibilite();
      appliquer();
    },
  };
}
