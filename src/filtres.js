import { CLASSES, PETIT_ECRAN, couchesVisibles } from './nitrates.js';
import { creer } from './dom.js';

const formaterNombre = (n) => n.toLocaleString('fr-FR');

// Filtres des couches de nitrates : classes (cases à cocher) et année de la dernière analyse (curseur).
// Les mêmes filtres s'appliquent à toutes les couches, par un filtre MapLibre sur chaque couche existante :
// les sources ne sont ni rechargées ni recréées. Seuls les points sont filtrés : les départements et le
// comportement du clic ne changent pas (une station filtrée n'est plus dessinée, donc plus cliquable).
// `couches` : [{ config, stations }] (voir ajouterNitrates). Renvoie majCompteurs, à rappeler quand une couche
// est affichée ou masquée.
export function ajouterFiltres(carte, couches) {
  const stations = couches.flatMap((couche) => couche.stations);
  if (stations.length === 0) return { majCompteurs() {} };

  // Années min. et max. lues dans les données (colonne date_analyse des CSV), jamais écrites en dur.
  let anneeMin = Infinity;
  let anneeMax = -Infinity;
  for (const s of stations) {
    anneeMin = Math.min(anneeMin, s.annee);
    anneeMax = Math.max(anneeMax, s.annee);
  }

  // Nombre de stations par couche, par classe et par année : les compteurs s'en déduisent sans reparcourir les stations.
  const comptes = couches.map(() => CLASSES.map(() => new Array(anneeMax - anneeMin + 1).fill(0)));
  couches.forEach((couche, i) => {
    for (const s of couche.stations) comptes[i][s.classe][s.annee - anneeMin] += 1;
  });

  const etat = { classes: new Set(CLASSES.keys()), annee: anneeMin };

  const titre = creer('summary', 'bloc-titre', 'Filtres');

  // Une case par classe, avec sa couleur et son libellé : tout est lu dans CLASSES.
  const unites = [...new Set(stations.map((s) => s.unite))].join(', ');
  const groupe = creer('fieldset', 'case-groupe');
  groupe.append(creer('legend', 'case-intitule', `Classes (${unites})`));
  const cases = CLASSES.map((classe, i) => {
    const caseACocher = creer('input');
    caseACocher.type = 'checkbox';
    caseACocher.checked = true;
    caseACocher.addEventListener('change', () => {
      if (caseACocher.checked) etat.classes.add(i);
      else etat.classes.delete(i);
      appliquer();
    });
    const pastille = creer('span', 'legende-pastille');
    pastille.style.background = classe.couleur;
    const ligne = creer('label', 'case-ligne');
    ligne.append(caseACocher, pastille, classe.libelle);
    groupe.append(ligne);
    return caseACocher;
  });

  const curseur = creer('input');
  curseur.type = 'range';
  curseur.id = 'filtre-annee';
  curseur.min = anneeMin;
  curseur.max = anneeMax;
  curseur.step = 1;
  curseur.value = anneeMin;
  curseur.disabled = anneeMin === anneeMax;
  curseur.addEventListener('input', () => {
    etat.annee = Number(curseur.value);
    appliquer();
  });
  const valeurAnnee = creer('output', 'filtres-annee-valeur', String(anneeMin));
  const etiquette = creer('label', 'filtres-etiquette');
  etiquette.htmlFor = curseur.id;
  etiquette.append('Analyses depuis ', valeurAnnee);
  const bornes = creer('div', 'filtres-bornes');
  bornes.append(creer('span', '', String(anneeMin)), creer('span', '', String(anneeMax)));
  const note = creer('p', 'legende-note', 'Année de la dernière analyse.');
  const annee = creer('div', 'filtres-annee');
  annee.append(etiquette, curseur, bornes, note);

  // Un compteur par couche visible : « Eaux souterraines : N stations affichées sur M ».
  const compteurs = couches.map(() => creer('p', 'filtres-compteur'));
  const aucune = creer('p', 'filtres-compteur', 'Aucune couche affichée.');
  const zoneCompteurs = creer('div', 'filtres-compteurs');
  zoneCompteurs.setAttribute('role', 'status');
  zoneCompteurs.append(...compteurs, aucune);

  const reinitialiser = creer('button', 'filtres-reinit', 'Réinitialiser');
  reinitialiser.type = 'button';
  reinitialiser.addEventListener('click', () => {
    etat.classes = new Set(CLASSES.keys());
    etat.annee = anneeMin;
    cases.forEach((c) => (c.checked = true));
    curseur.value = anneeMin;
    appliquer();
  });

  function majCompteurs() {
    valeurAnnee.textContent = String(etat.annee);
    const visibles = new Set(couchesVisibles(carte).map((config) => config.id));
    couches.forEach(({ config, stations: deLaCouche }, i) => {
      let affichees = 0;
      for (const c of etat.classes) {
        for (let a = etat.annee; a <= anneeMax; a++) affichees += comptes[i][c][a - anneeMin];
      }
      const libelle = affichees > 1 ? 'stations affichées' : 'station affichée';
      compteurs[i].textContent = `${config.nom} : ${formaterNombre(affichees)} ${libelle} sur ${formaterNombre(deLaCouche.length)}`;
      compteurs[i].hidden = !visibles.has(config.id);
    });
    aucune.hidden = visibles.size > 0;
  }

  function appliquer() {
    const filtre = [
      'all',
      ['in', ['get', 'classe'], ['literal', [...etat.classes]]],
      ['>=', ['get', 'annee'], etat.annee],
    ];
    for (const { config } of couches) carte.setFilter(config.id, filtre);
    majCompteurs();
  }

  majCompteurs();
  const bloc = document.getElementById('filtres');
  bloc.replaceChildren(titre, groupe, annee, zoneCompteurs, reinitialiser);
  bloc.open = !window.matchMedia(PETIT_ECRAN).matches;
  bloc.hidden = false;
  return { majCompteurs };
}
