# Carte de France

Carte interactive de la France métropolitaine, 100 % côté navigateur : **pas de backend**.
Les données sont des fichiers statiques dans `data/`, chargés par le navigateur.

## Stack

- Vite + MapLibre GL JS, en JavaScript simple (modules ES, pas de TypeScript ni de framework).
- Fond de carte : OpenFreeMap « positron » (gratuit, sans clé API). L'URL du style est la constante
  `STYLE_FOND` dans `src/main.js`. Ne pas introduire de service nécessitant une clé API ou un serveur.

## Commandes

- `npm install` : installer les dépendances
- `npm run dev` : serveur de développement (http://localhost:5173)
- `npm run build` : build statique dans `dist/` (`base: './'`, déployable dans un sous-chemin)
- `npm run preview` : prévisualiser le build

Il n'y a pas encore de tests ni de linter.

## Structure

- `src/main.js` : création de la carte, source et couche des départements
- `src/locale-fr.js` : traduction des textes de l'interface MapLibre
- `src/style.css` : styles de la page
- `data/` : données géographiques (`departements.geojson`, 96 départements métropolitains, propriétés `code` et `nom`)
- `public/` : fichiers servis tels quels (favicon)

## Conventions

- **Codes INSEE toujours en texte.** Département (`"01"`, `"2A"`, `"2B"`, `"75"`), commune (5 caractères : `"01001"`, `"2A004"`).
  Ne jamais les convertir en nombre (`Number`, `parseInt`, `+code`) : on perdrait le zéro initial et `2A`/`2B` n'existent pas en nombre.
  Comparer des chaînes (`['==', ['get', 'code'], '2A']`), lire les CSV sans inférence de types,
  et utiliser `promoteId: 'code'` plutôt que des identifiants numériques pour `feature-state`.
- **Coordonnées en WGS84** (EPSG:4326, degrés), dans l'ordre `[longitude, latitude]` attendu par MapLibre et GeoJSON.
  Reprojeter toute donnée source en Lambert-93 (EPSG:2154) ou autre avant de l'ajouter à `data/`.
- **Interface en français** : textes visibles, `lang="fr"`, infobulles et attributions.
  Les textes MapLibre sont traduits dans `src/locale-fr.js` ; tout nouveau contrôle doit y trouver ses libellés.
  Le code (identifiants, commentaires) est aussi en français.
- Écrire du code simple, sans abstraction anticipée.

## Notes techniques

- MapLibre 6 n'a pas d'export par défaut : `import * as maplibregl from 'maplibre-gl'`.
- Son worker est un fichier séparé que Vite n'embarque pas : `src/main.js` l'importe avec `?url`
  et appelle `setWorkerUrl` avant de créer la carte. Sans cela : erreur « Worker failed to load ».
- Les fichiers GeoJSON sont importés avec `?url` et chargés par MapLibre.
- Les contours des départements sont insérés sous la première couche de texte du fond de carte, pour garder les étiquettes lisibles.

## Données

- `data/departements.geojson` : [gregoiredavid/france-geojson](https://github.com/gregoiredavid/france-geojson),
  `departements-version-simplifiee.geojson` (tracés IGN Admin Express COG 2018 simplifiés, codes INSEE).
  Licence ouverte Etalab : conserver la mention de la source (attribution de la source dans `src/main.js`).
