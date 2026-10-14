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

## Déploiement

- GitHub Pages, via `.github/workflows/deploy.yml` : `npm ci` puis `npm run build` (Node 22), publication de `dist/`
  à chaque push sur `main` (ou lancement manuel). Aucune branche autre que `main` ne déploie.
- Le site est servi dans un sous-chemin (`/carte-france/`) : garder `base: './'` dans `vite.config.js`
  et ne jamais écrire de chemin absolu (`/data/...`) pour un fichier de données ou une image. Importer les fichiers avec `?url`.
- Pour vérifier un déploiement en local : copier `dist/` dans un dossier `carte-france/`, servir son parent
  avec un serveur statique, puis ouvrir `/carte-france/`.

## Structure

- `src/main.js` : création de la carte et de ses contrôles
- `src/departements.js` : source et couches des départements, survol, sélection, fenêtre d'information
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
- Les couches des départements sont insérées sous la première couche de texte du fond de carte, pour garder les étiquettes lisibles.
- Interaction (`src/departements.js`) : la couche `departements-fond` (surface, transparente au repos) détecte le département
  touché et porte le surlignage. Deux états `feature-state`, identifiés par le code INSEE en texte (`promoteId: 'code'`) :
  `survol` (léger) et `selectionne` (marqué, contour épaissi). La sélection dure jusqu'à un clic hors des départements
  ou la croix de la fenêtre ; une seule fenêtre existe à la fois, réutilisée.
- L'événement `click` de MapLibre couvre la souris et le toucher (un appui, pas un glissement). Le survol n'est branché que si
  `(hover: hover) and (pointer: fine)` : sur écran tactile, il resterait bloqué après un appui.
- Le contenu de la fenêtre est créé une seule fois et seulement mis à jour. Appeler `setDOMContent`/`setHTML` sur une fenêtre
  déjà ouverte recrée sa croix de fermeture sans son `aria-label`.
- Sous 560 px de large, la fenêtre devient un bandeau pleine largeur en haut de l'écran (voir `src/style.css`) : ancrée au point
  touché, elle dépasserait de l'écran dès qu'elle fait plus de la moitié de la largeur. En bas, elle passerait sous les crédits,
  qui occupent plusieurs lignes sur téléphone.
- Vérifier une interaction avec de vrais appuis (`page.touchscreen.tap` de Playwright, `hasTouch`) sur 390×844, 360×640 et 320×568,
  puis regarder les captures : des mesures de position ne remplacent pas un coup d'œil (le recouvrement des crédits n'a été vu qu'ainsi).

## Données

- `data/departements.geojson` : [gregoiredavid/france-geojson](https://github.com/gregoiredavid/france-geojson),
  `departements-version-simplifiee.geojson` (tracés IGN Admin Express COG 2018 simplifiés, codes INSEE).
  Licence ouverte Etalab : conserver la mention de la source (attribution de la source dans `src/departements.js`).
