# Carte de France

Carte interactive de la France métropolitaine, entièrement côté navigateur (pas de backend) :
[Vite](https://vite.dev) + [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/).

La carte affiche les contours des départements sur un fond sobre et gratuit,
[OpenFreeMap](https://openfreemap.org) (style « positron »), sans clé API.

Un clic (ou un appui sur téléphone) sur un département ouvre une fenêtre avec son nom et son code INSEE.
Le département reste surligné jusqu'à un clic ailleurs ou sur la croix de la fenêtre.
Sur ordinateur, le département sous le curseur est aussi surligné.

## Lancer le projet

Prérequis : Node.js 20.19+ ou 22.12+.

```bash
npm install
npm run dev      # serveur de développement : http://localhost:5173
npm run build    # version statique dans dist/
npm run preview  # prévisualiser dist/
```

Le contenu de `dist/` peut être hébergé tel quel sur n'importe quel hébergement statique.

## Déploiement (GitHub Pages)

Chaque fusion sur `main` construit le site et le publie, via `.github/workflows/deploy.yml`.
Le workflow peut aussi être lancé à la main depuis l'onglet « Actions ».

Réglage à faire une seule fois : dans le dépôt, **Settings → Pages → Build and deployment → Source : GitHub Actions**.
Le site est ensuite publié sur <https://2026-anon.github.io/carte-france/>.

## Structure

- `src/` : code de l'application (`main.js`, `style.css`, textes français de MapLibre).
- `data/` : données géographiques (contours des départements au format GeoJSON).
- `public/` : fichiers servis tels quels (icône du site).

## Données et crédits

- Contours et codes des départements : [france-geojson](https://github.com/gregoiredavid/france-geojson)
  (IGN Admin Express COG 2018, INSEE), sous Licence ouverte Etalab.
- Fond de carte : © contributeurs [OpenStreetMap](https://www.openstreetmap.org/copyright), via OpenFreeMap.

Voir `CLAUDE.md` pour les conventions du projet.
