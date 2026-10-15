# Carte de France

Carte interactive de la France métropolitaine, entièrement côté navigateur (pas de backend) :
[Vite](https://vite.dev) + [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/).

La carte affiche les contours des départements sur un fond sobre et gratuit,
[OpenFreeMap](https://openfreemap.org) (style « positron »), sans clé API.

La carte affiche aussi les nitrates dans les eaux : les eaux souterraines (stations ADES / Hub'Eau) et les eaux de surface (stations Naïades / Hub'Eau),
selon les mêmes 5 classes autour du seuil de 50 mg/L, donc comparables. Le remplissage d'un point dit sa classe ; le contour dit la couche
(trait blanc fin pour les eaux souterraines, contour bleu foncé plus épais pour les eaux de surface). Un clic sur une station ouvre sa fiche
(voir `CLAUDE.md` pour mettre les données à jour).
Un bloc « Couches » affiche ou masque chaque couche. Un bloc « Filtres » permet de masquer des classes et de ne garder que les stations analysées
depuis une année donnée, pour les deux couches, avec le nombre de stations affichées par couche. Couches, filtres et légende sont repliés par défaut sur petit écran.

Le réseau ferré national (lignes et gares, données SNCF Réseau, ODbL) est une couche à part, décochée au départ : ses deux sous-couches,
les lignes et les gares, se cochent séparément dans le bloc « Couches » et ne sont chargées qu'à la première activation. Les lignes suivent la légende
de la carte « Le réseau ferré en France » (LGV, lignes mixtes et fret, non exploitées, suspendues ; 1, 2 ou 3 traits selon les voies ; traits perpendiculaires
pour l'électrification) et les gares trois niveaux d'intérêt, qui apparaissent progressivement avec le zoom. Des filtres et une légende leur sont dédiés.
`python3 scripts/preparer_rfn.py` (Python 3 et numpy) régénère ces données ; les écarts avec la légende officielle sont listés dans `CLAUDE.md`.

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
