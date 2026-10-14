import * as maplibregl from 'maplibre-gl';
import nitratesUrl from '../data/nitrates_stations.csv?url';

const SOURCE = 'nitrates';
export const COUCHE_NITRATES = 'nitrates-points';

// 5 classes en mg(NO3)/L, alignées sur la limite de qualité de l'eau potable : 50 mg/L.
// Une valeur égale à la borne haute appartient à la classe ; au-dessus de 50, la limite est dépassée.
const CLASSES = [
  { max: 10, couleur: '#4575b4', libelle: '10 ou moins' },
  { max: 25, couleur: '#91bfdb', libelle: 'De 10 à 25' },
  { max: 50, couleur: '#fee090', libelle: 'De 25 à 50' },
  { max: 100, couleur: '#fc8d59', libelle: 'De 50 à 100 (limite dépassée)' },
  { max: Infinity, couleur: '#d73027', libelle: 'Plus de 100' },
];

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
        valeur: Number(s.valeur),
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
function expressionCouleur() {
  const cas = [];
  CLASSES.slice(0, -1).forEach((classe) => cas.push(['<=', ['get', 'valeur'], classe.max], classe.couleur));
  return ['case', ...cas, CLASSES[CLASSES.length - 1].couleur];
}

function remplirLegende(stations) {
  const dates = stations.map((s) => s.date_analyse).sort();
  const unite = stations[0].unite;
  const legende = document.getElementById('legende');
  // Le titre sert de bouton : sur petit écran, on peut replier la légende pour dégager la carte.
  const titre = document.createElement('summary');
  titre.className = 'legende-titre';
  titre.textContent = `Nitrates dans les eaux souterraines (${unite})`;
  const liste = document.createElement('ul');
  for (const classe of CLASSES) {
    const item = document.createElement('li');
    const pastille = document.createElement('span');
    pastille.className = 'legende-pastille';
    pastille.style.background = classe.couleur;
    item.append(pastille, classe.libelle);
    liste.append(item);
  }
  const periode = document.createElement('p');
  periode.className = 'legende-note';
  periode.textContent =
    `Dernière analyse de chaque station, du ${formaterDate(dates[0])} au ${formaterDate(dates[dates.length - 1])}.`;
  legende.replaceChildren(titre, liste, periode);
  legende.hidden = false;
}

export async function ajouterNitrates(carte) {
  const reponse = await fetch(nitratesUrl);
  const stations = lireCsv(await reponse.text()).filter((s) => s.code_station);

  carte.addSource(SOURCE, {
    type: 'geojson',
    data: enGeoJson(stations),
    attribution: 'Nitrates : ADES / Hub’Eau (eaufrance.fr), Licence ouverte Etalab 2.0',
  });

  // Même position que les départements (sous les étiquettes du fond), ajoutée après : donc au-dessus.
  const premiereCoucheTexte = carte.getStyle().layers.find((couche) => couche.type === 'symbol')?.id;
  carte.addLayer(
    {
      id: COUCHE_NITRATES,
      type: 'circle',
      source: SOURCE,
      layout: { 'circle-sort-key': ['get', 'valeur'] }, // les valeurs fortes restent visibles au-dessus
      paint: {
        'circle-color': expressionCouleur(),
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 2.5, 8, 4.5, 11, 8],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 0.8,
        'circle-opacity': 0.9,
      },
    },
    premiereCoucheTexte,
  );

  remplirLegende(stations);
  activerInteraction(carte);
}

function activerInteraction(carte) {
  // Contenu créé une fois, seulement mis à jour (voir src/departements.js).
  const ligne = (classe) => {
    const p = document.createElement('p');
    p.className = classe;
    return p;
  };
  const elementNom = ligne('station-nom');
  const elementCommune = ligne('station-detail');
  const elementValeur = ligne('station-valeur');
  const elementDate = ligne('station-detail');
  const elementCode = ligne('station-detail');
  const contenu = document.createElement('div');
  contenu.append(elementNom, elementCommune, elementValeur, elementDate, elementCode);

  const fenetre = new maplibregl.Popup({
    className: 'fenetre-station',
    closeOnClick: false,
    maxWidth: '300px',
    offset: 10,
  }).setDOMContent(contenu);

  // Le clic sur un point prime sur celui du département (voir src/departements.js, qui ignore ce clic).
  carte.on('click', (e) => {
    const point = carte.queryRenderedFeatures(e.point, { layers: [COUCHE_NITRATES] })[0];
    if (!point) {
      fenetre.remove();
      return;
    }
    const s = point.properties;
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
    carte.on('mouseenter', COUCHE_NITRATES, () => (carte.getCanvas().style.cursor = 'pointer'));
    carte.on('mouseleave', COUCHE_NITRATES, () => (carte.getCanvas().style.cursor = ''));
  }
}
