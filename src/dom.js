// Crée un élément avec une classe et un texte (jamais de HTML : les textes ne sont pas interprétés).
export function creer(balise, classe, texte) {
  const element = document.createElement(balise);
  if (classe) element.className = classe;
  if (texte !== undefined) element.textContent = texte;
  return element;
}
