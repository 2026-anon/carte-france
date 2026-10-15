import * as maplibregl from 'maplibre-gl';
import { creer } from './dom.js';
import urlSouterraines from '../data/nitrates_stations.csv?url';
import urlSurface from '../data/nitrates_cours_eau.csv?url';

// Petit écran : le bloc des couches, les filtres et la légende sont repliés au départ.
export const PETIT_ECRAN = '(max-width: 599px)';

// SEULE définition des classes : les bornes, les libellés et les couleurs. Les deux couches la partagent, pour être
// comparables. La légende, la couleur des cercles et les filtres (src/filtres.js) la lisent ; ne jamais recopier
// ces valeurs ailleurs.
// 5 classes en mg(NO3)/L, alignées sur la limite de qualité de l'eau potable : 50 mg/L.
// Une valeur égale à la borne haute appartient à la classe ; au-dessus de 50, la limite est dépassée.
export const CLASSES = [
  { max: 10, couleur: '#4575b4', libelle: '10 ou moins' },
  { max: 25, couleur: '#91bfdb', libelle: 'De 10 à 25' },
  { max: 50, couleur: '#fee090', libelle: 'De 25 à 50' },
  { max: 100, couleur: '#fc8d59', libelle: 'De 50 à 100 (limite dépassée)' },
  { max: Infinity, couleur: '#d73027', libelle: 'Plus de 100' },
];

// SEULE définition des couches : une configuration par couche, les deux partageant CLASSES. Pour en ajouter une, il suffit
// d'ajouter une entrée (et son CSV) ; le chargement, la légende, les filtres, le bloc des couches et la fenêtre la lisent.
// - id : celui du catalogue data/layers.csv ; sert aussi d'identifiant à la source et à la couche MapLibre ;
// - nom : libellé court (bloc des couches, compteurs, légende) ; libelleFenetre : type affiché dans la fenêtre de la station ;
// - contour : couleur, épaisseur en pixels aux zooms 4 et 8 (le remplissage reste celui de la classe), description pour la légende.
// L'ordre est celui du dessin : la dernière couche est dessinée au-dessus.
export const COUCHES = [
  {
    id: 'nitrates_eaux_souterraines',
    nom: 'Eaux souterraines',
    libelleFenetre: 'Eaux souterraines (ADES)',
    fichier: urlSouterraines,
    contour: { couleur: '#ffffff', largeur: [0.2, 0.7], description: 'Trait blanc fin' },
    attribution: 'Nitrates : ADES / Hub’Eau (eaufrance.fr), Licence ouverte Etalab 2.0',
  },
  {
    id: 'nitrates_eaux_surface',
    nom: 'Eaux de surface',
    libelleFenetre: 'Eaux de surface (Naïades)',
    fichier: urlSurface,
    contour: { couleur: '#0b2d5e', largeur: [0.2, 1.1], description: 'Contour bleu foncé' },
    attribution: 'Nitrates : Naïades / Hub’Eau (eaufrance.fr), Licence ouverte Etalab 2.0',
  },
];

// Indice de la classe d'une valeur : la première dont la borne haute la contient.
const classeDe = (valeur) => CLASSES.findIndex((classe) => valeur <= classe.max);

// Marge de tolérance autour du doigt ou du curseur, en pixels : les points sont petits.
const MARGE_TOUCHER = 14;
const MARGE_SOURIS = 3;

const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

// Lit un CSV avec guillemets. Tout reste du texte : les codes ("01", "2A") ne sont jamais convertis en nombre.
function lireCsv(texte) {
  const lignes = [];
  let ligne = [];
  let champ = '';
  let entreGuillemets = false;
  for (let i = 0; i < texte.length; i++) {
    const c = texte[i];
    if (entreGuillemets) {
      if (c === '"' && texte[i + 1] === '"') {
        champ += '"';
        i++;
      } else if (c === '"') {
        entreGuillemets = false;
      } else {
        champ += c;
      }
    } else if (c === '"') {
      entreGuillemets = true;
    } else if (c === ',') {
      ligne.push(champ);
      champ = '';
    } else if (c === '\n') {
      ligne.push(champ);
      lignes.push(ligne);
      ligne = [];
      champ = '';
    } else if (c !== '\r') {
      champ += c;
    }
  }
  if (champ !== '' || ligne.length > 0) {
    ligne.push(champ);
    lignes.push(ligne);
  }
  const [entete, ...donnees] = lignes;
  return donnees.map((valeurs) => Object.fromEntries(entete.map((nom, i) => [nom, valeurs[i]])));
}

function enGeoJson(stations) {
  return {
    type: 'FeatureCollection',
    features: stations.map((s) => ({
      type: 'Feature',
      // GeoJSON : [longitude, latitude]
      geometry: { type: 'Point', coordinates: [Number(s.lon), Number(s.lat)] },
      properties: {
        code_station: s.code_station,
        nom: s.nom,
        commune: s.commune,
        code_dept: s.code_dept,
        date_analyse: s.date_analyse,
        annee: s.annee,
        valeur: s.valeur,
        classe: s.classe,
        unite: s.unite,
      },
    })),
  };
}

function formaterDate(aaaammjj) {
  const [a, m, j] = aaaammjj.split('-');
  return `${Number(j)} ${MOIS[Number(m) - 1]} ${a}`;
}

const formaterValeur = (valeur) => valeur.toLocaleString('fr-FR', { maximumFractionDigits: 2 });

// Couleur de chaque point selon sa classe.
const expressionCouleur = () => ['to-color', ['at', ['get', 'classe'], ['literal', CLASSES.map((classe) => classe.couleur)]]];

// Symbole du contour d'une couche (légende et bloc des couches) : un disque neutre, cerclé comme sur la carte.
export function symboleContour({ couleur, largeur }) {
  const symbole = creer('span', 'legende-symbole');
  symbole.style.border = `${Math.max(1.5, largeur[1] * 2.5)}px solid ${couleur}`;
  return symbole;
}

function remplirLegende(couches) {
  const stations = couches.flatMap((couche) => couche.stations);
  const dates = stations.map((s) => s.date_analyse).sort();
  const unites = [...new Set(stations.map((s) => s.unite))].join(', ');
  const legende = document.getElementById('legende');
  // Le titre sert de bouton : sur petit écran, on peut replier la légende pour dégager la carte.
  const titre = creer('summary', 'bloc-titre', `Nitrates (${unites})`);
  const classes = creer('ul');
  for (const classe of CLASSES) {
    const pastille = creer('span', 'legende-pastille');
    pastille.style.background = classe.couleur;
    const item = creer('li');
    item.append(pastille, classe.libelle);
    classes.append(item);
  }
  // Le remplissage dit la classe ; le contour dit la couche.
  const contours = creer('ul');
  for (const { config } of couches) {
    const item = creer('li');
    item.append(symboleContour(config.contour), `${config.contour.description} : ${config.nom.toLowerCase()}`);
    contours.append(item);
  }
  const periode = creer('p', 'legende-note',
    `Dernière analyse de chaque station, du ${formaterDate(dates[0])} au ${formaterDate(dates[dates.length - 1])}.`);
  legende.replaceChildren(titre, classes, creer('p', 'legende-sous-titre', 'Contour des cercles'), contours, periode);
  legende.open = !window.matchMedia(PETIT_ECRAN).matches;
  legende.hidden = false;
}

// Une station sans valeur ni date lisibles ne peut pas être classée : elle est ignorée.
const estLisible = (s) => s.code_station && Number.isFinite(Number(s.valeur)) && /^\d{4}-\d{2}-\d{2}$/.test(s.date_analyse);

// Charge le CSV d'une couche : stations typées, avec leur classe et l'année de leur dernière analyse.
async function chargerCouche(config) {
  const reponse = await fetch(config.fichier);
  const stations = lireCsv(await reponse.text())
    .filter(estLisible)
    .map((s) => ({
      ...s,
      valeur: Number(s.valeur),
      classe: classeDe(Number(s.valeur)),
      annee: Number(s.date_analyse.slice(0, 4)), // année de la dernière analyse de la station
    }));
  return { config, stations };
}

// Ajoute toutes les couches de COUCHES ; renvoie [{ config, stations }] pour les filtres et le bloc des couches.
export async function ajouterNitrates(carte) {
  const couches = await Promise.all(COUCHES.map(chargerCouche));

  // Même position que les départements (sous les étiquettes du fond), ajoutées après : donc au-dessus.
  const premiereCoucheTexte = carte.getStyle().layers.find((couche) => couche.type === 'symbol')?.id;
  for (const { config, stations } of couches) {
    carte.addSource(config.id, { type: 'geojson', data: enGeoJson(stations), attribution: config.attribution });
    carte.addLayer(
      {
        id: config.id,
        type: 'circle',
        source: config.id,
        layout: { 'circle-sort-key': ['get', 'valeur'] }, // les valeurs fortes restent visibles au-dessus
        paint: {
          'circle-color': expressionCouleur(),
          // Petits sur la vue France entière (plus de 35 000 points), plus grands quand on zoome ; l'opacité réduite
          // et le trait fin laissent voir les zones denses au lieu d'un aplat.
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 1.4, 6, 2, 8, 3.8, 11, 7, 14, 10],
          'circle-stroke-color': config.contour.couleur,
          'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 4, config.contour.largeur[0], 8, config.contour.largeur[1]],
          'circle-opacity': 0.8,
        },
      },
      premiereCoucheTexte,
    );
  }

  remplirLegende(couches);
  activerInteraction(carte);
  return couches;
}

// Couches affichées : une couche masquée n'est ni dessinée ni cliquable.
export const couchesVisibles = (carte) =>
  COUCHES.filter((config) => carte.getLayer(config.id) && carte.getLayoutProperty(config.id, 'visibility') !== 'none');

// Stations sous un appui ou un clic, dans les couches visibles, de la plus proche à la plus éloignée (à égalité : la valeur
// la plus forte, celle qui est dessinée au-dessus). Une marge de tolérance entoure le point, plus large au doigt qu'à la souris.
export function stationsSous(carte, point) {
  const couches = couchesVisibles(carte).map((config) => config.id);
  if (couches.length === 0) return [];
  const marge = window.matchMedia('(pointer: coarse)').matches ? MARGE_TOUCHER : MARGE_SOURIS;
  const zone = [
    [point.x - marge, point.y - marge],
    [point.x + marge, point.y + marge],
  ];
  const distance = (station) => {
    const position = carte.project(station.geometry.coordinates);
    return Math.hypot(position.x - point.x, position.y - point.y);
  };
  return carte
    .queryRenderedFeatures(zone, { layers: couches })
    .map((station) => ({ station, ecart: distance(station) }))
    .sort((a, b) => a.ecart - b.ecart || b.station.properties.valeur - a.station.properties.valeur)
    .map(({ station }) => station);
}

function activerInteraction(carte) {
  // Contenu créé une fois, seulement mis à jour (voir src/departements.js).
  const elementType = creer('p', 'station-type');
  const elementNom = creer('p', 'station-nom');
  const elementCommune = creer('p', 'station-detail');
  const elementValeur = creer('p', 'station-valeur');
  const elementDate = creer('p', 'station-detail');
  const elementCode = creer('p', 'station-detail');
  const contenu = creer('div');
  contenu.append(elementType, elementNom, elementCommune, elementValeur, elementDate, elementCode);

  const fenetre = new maplibregl.Popup({
    className: 'fenetre-station',
    closeOnClick: false,
    maxWidth: '300px',
    offset: 10,
  }).setDOMContent(contenu);

  // Le clic sur un point d'une couche visible prime sur celui du département (voir src/departements.js, qui ignore ce clic).
  carte.on('click', (e) => {
    const point = stationsSous(carte, e.point)[0];
    if (!point) {
      fenetre.remove();
      return;
    }
    const s = point.properties;
    elementType.textContent = COUCHES.find((config) => config.id === point.layer.id).libelleFenetre;
    elementNom.textContent = s.nom;
    elementCommune.textContent = `Commune : ${s.commune || 'inconnue'} (${s.code_dept})`;
    elementValeur.textContent = `${formaterValeur(s.valeur)} ${s.unite}`;
    elementDate.textContent = `Analyse du ${formaterDate(s.date_analyse)}`;
    elementCode.textContent = `Code de la station : ${s.code_station}`;
    fenetre.setLngLat(point.geometry.coordinates);
    if (!fenetre.isOpen()) fenetre.addTo(carte);
  });

  const survolable = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  if (survolable) {
    for (const { id } of COUCHES) {
      carte.on('mouseenter', id, () => (carte.getCanvas().style.cursor = 'pointer'));
      carte.on('mouseleave', id, () => (carte.getCanvas().style.cursor = ''));
    }
  }
}
