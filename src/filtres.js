import { CLASSES, COUCHE_NITRATES, PETIT_ECRAN } from './nitrates.js';

const formaterNombre = (n) => n.toLocaleString('fr-FR');

function creer(balise, classe, texte) {
  const element = document.createElement(balise);
  if (classe) element.className = classe;
  if (texte !== undefined) element.textContent = texte;
  return element;
}

// Filtres de la couche nitrates : classes (cases à cocher) et année de la dernière analyse (curseur).
// Ils agissent par un filtre MapLibre sur la couche existante : la source n'est ni rechargée ni recréée.
// Seuls les points sont filtrés : les départements et le comportement du clic ne changent pas.
export function ajouterFiltres(carte, stations) {
  if (stations.length === 0) return;
  const total = stations.length;

  // Années min. et max. lues dans les données (colonne date_analyse du CSV), jamais écrites en dur.
  let anneeMin = Infinity;
  let anneeMax = -Infinity;
  for (const s of stations) {
    anneeMin = Math.min(anneeMin, s.annee);
    anneeMax = Math.max(anneeMax, s.annee);
  }

  // Nombre de stations par classe et par année : le compteur s'en déduit sans reparcourir les stations.
  const comptes = CLASSES.map(() => new Array(anneeMax - anneeMin + 1).fill(0));
  for (const s of stations) comptes[s.classe][s.annee - anneeMin] += 1;

  const etat = { classes: new Set(CLASSES.keys()), annee: anneeMin };

  const titre = creer('summary', 'bloc-titre', 'Filtres');

  // Une case par classe, avec sa couleur et son libellé : tout est lu dans CLASSES.
  const groupe = creer('fieldset', 'filtres-classes');
  groupe.append(creer('legend', 'filtres-intitule', `Classes (${stations[0].unite})`));
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
    const ligne = creer('label', 'filtres-ligne');
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

  const compteur = creer('p', 'filtres-compteur');
  compteur.setAttribute('role', 'status');

  const reinitialiser = creer('button', 'filtres-reinit', 'Réinitialiser');
  reinitialiser.type = 'button';
  reinitialiser.addEventListener('click', () => {
    etat.classes = new Set(CLASSES.keys());
    etat.annee = anneeMin;
    cases.forEach((c) => (c.checked = true));
    curseur.value = anneeMin;
    appliquer();
  });

  function majCompteur() {
    valeurAnnee.textContent = String(etat.annee);
    let affichees = 0;
    for (const i of etat.classes) {
      for (let a = etat.annee; a <= anneeMax; a++) affichees += comptes[i][a - anneeMin];
    }
    const libelle = affichees > 1 ? 'stations affichées' : 'station affichée';
    compteur.textContent = `${formaterNombre(affichees)} ${libelle} sur ${formaterNombre(total)}`;
  }

  function appliquer() {
    carte.setFilter(COUCHE_NITRATES, [
      'all',
      ['in', ['get', 'classe'], ['literal', [...etat.classes]]],
      ['>=', ['get', 'annee'], etat.annee],
    ]);
    majCompteur();
  }

  majCompteur();
  const bloc = document.getElementById('filtres');
  bloc.replaceChildren(titre, groupe, annee, compteur, reinitialiser);
  bloc.open = !window.matchMedia(PETIT_ECRAN).matches;
  bloc.hidden = false;
}
