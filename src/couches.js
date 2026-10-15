import { PETIT_ECRAN, symboleContour } from './nitrates.js';
import { creer } from './dom.js';

// Bloc « Couches » : une case par couche pour l'afficher ou la masquer. Une couche masquée n'est ni dessinée ni cliquable
// (voir stationsSous dans src/nitrates.js). `quandChange` est rappelée après chaque changement (compteurs des filtres).
// `rail` (src/rail.js) apporte deux sous-couches, les lignes et les gares du réseau ferré, décochées au départ et chargées à
// la première activation.
export function ajouterCouches(carte, couches, quandChange, rail) {
  const titre = creer('summary', 'bloc-titre', 'Couches');
  const groupe = creer('div', 'case-groupe');
  groupe.setAttribute('role', 'group');
  groupe.setAttribute('aria-label', 'Couches affichées');
  for (const { config } of couches) {
    const caseACocher = creer('input');
    caseACocher.type = 'checkbox';
    caseACocher.checked = true;
    caseACocher.addEventListener('change', () => {
      carte.setLayoutProperty(config.id, 'visibility', caseACocher.checked ? 'visible' : 'none');
      quandChange();
    });
    const ligne = creer('label', 'case-ligne');
    ligne.append(caseACocher, symboleContour(config.contour), config.nom);
    groupe.append(ligne);
  }

  const groupeRail = creer('div', 'case-groupe');
  groupeRail.setAttribute('role', 'group');
  groupeRail.setAttribute('aria-label', 'Réseau ferré national');
  groupeRail.append(creer('p', 'case-intitule', 'Réseau ferré national'));
  const etatRail = creer('p', 'filtres-compteur');
  etatRail.setAttribute('role', 'status');
  for (const sousCouche of rail.sousCouches) {
    const caseACocher = creer('input');
    caseACocher.type = 'checkbox';
    caseACocher.addEventListener('change', async () => {
      // Le premier affichage charge les données : la case est bloquée pendant ce temps, et rendue en cas d'échec.
      caseACocher.disabled = true;
      etatRail.textContent = caseACocher.checked ? `Chargement : ${sousCouche.nom.toLowerCase()}…` : '';
      try {
        await rail.afficher(sousCouche.id, caseACocher.checked);
        etatRail.textContent = '';
      } catch {
        caseACocher.checked = false;
        etatRail.textContent = `Chargement impossible : ${sousCouche.nom.toLowerCase()}.`;
        await rail.afficher(sousCouche.id, false).catch(() => {});
      }
      caseACocher.disabled = false;
    });
    const ligne = creer('label', 'case-ligne');
    ligne.append(caseACocher, sousCouche.nom);
    groupeRail.append(ligne);
  }
  groupeRail.append(etatRail);

  const bloc = document.getElementById('couches');
  bloc.replaceChildren(titre, groupe, groupeRail);
  bloc.open = !window.matchMedia(PETIT_ECRAN).matches;
  bloc.hidden = false;
}
