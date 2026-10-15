import { PETIT_ECRAN, symboleContour } from './nitrates.js';
import { creer } from './dom.js';

// Bloc « Couches » : une case par couche pour l'afficher ou la masquer. Une couche masquée n'est ni dessinée ni cliquable
// (voir stationsSous dans src/nitrates.js). `quandChange` est rappelée après chaque changement (compteurs des filtres).
export function ajouterCouches(carte, couches, quandChange) {
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

  const bloc = document.getElementById('couches');
  bloc.replaceChildren(titre, groupe);
  bloc.open = !window.matchMedia(PETIT_ECRAN).matches;
  bloc.hidden = false;
}
