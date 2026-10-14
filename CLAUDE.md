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
- `src/nitrates.js` : couche des stations de nitrates (cercles), légende, fenêtre d'information
- `src/style.css` : styles de la page
- `data/` : données géographiques (`departements.geojson`, 96 départements métropolitains, propriétés `code` et `nom`)
- `scripts/fetch_nitrates.py` : mise à jour de `data/nitrates_stations.csv` depuis Hub'Eau
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
- `data/nitrates_stations.csv` : nitrates dans les eaux souterraines, API Hub'Eau « Qualité des nappes d'eau souterraine »
  (`/v1/qualite_nappes/analyses`, paramètre 1340), données ADES, Licence ouverte Etalab 2.0 (attribution dans `src/nitrates.js`).
  Une ligne par station : la dernière analyse parmi celles des 5 dernières années. Colonnes : `code_station` (texte, `bss_id`),
  `nom` (ancien code BSS : l'API ne fournit pas de nom de station), `lat`, `lon` (WGS84, 4 décimales), `commune`,
  `code_dept` (texte), `date_analyse` (AAAA-MM-JJ), `valeur`, `unite` (telle que renvoyée : `mg(NO3)/L`).
- `data/layers.csv` : catalogue des couches (`id,nom,fichier,type,cle_jointure,colonne_valeur,filtres,palette,unite,source`).
  Documentation seulement : le code ne le lit pas encore, les réglages de la couche sont dans `src/nitrates.js`.

### Mettre à jour les nitrates

`python3 scripts/fetch_nitrates.py` (Python 3 standard, aucune dépendance ; environ 25 minutes : une requête par département,
l'API est lente). Il réécrit `data/nitrates_stations.csv` et affiche le nombre de stations, celles ignorées et les unités.
Limites de l'API respectées : page de 5000 au plus (max 20000) et profondeur `page × taille` ≤ 20000, d'où le découpage par
département (et par période au-delà de 20000 analyses). La fenêtre est `aujourd'hui − 5 ans`.

### Conventions de la couche nitrates

- Cercles MapLibre (`circle`), jamais de marqueurs HTML, sous les étiquettes du fond et au-dessus des départements.
- 5 classes en mg(NO3)/L, alignées sur la limite de qualité de 50 mg/L : ≤ 10, ≤ 25, ≤ 50, ≤ 100, > 100 (la borne haute
  est incluse ; au-dessus de 50, la limite est dépassée). Les mêmes bornes servent à la couleur des points et à la légende.
- Une station dont la dernière analyse n'a pas de valeur ou de coordonnées est ignorée (on ne retombe pas sur une analyse plus ancienne).
- Ne jamais mélanger deux unités sans conversion explicite : le script affiche les unités rencontrées, une seule (`mg(NO3)/L`) à ce jour.
- Clic ou toucher sur un point : fenêtre de la station (`.fenetre-station`), et le clic sur un point prime sur celui du département
  (`src/departements.js` l'ignore et ferme sa fenêtre). Même bandeau pleine largeur que les départements sous 560 px.
- La légende (`<details id="legende">`) est repliable ; sous 560 px elle est remontée à `bottom: 96px` pour ne pas passer sous les crédits.
- Le CSV (≈ 1,9 Mo) est chargé par le navigateur avec `?url` puis converti en GeoJSON ; sa limite de poids visée est ~10 Mo.
