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
- `src/nitrates.js` : couche des stations de nitrates (cercles), **définition des classes (`CLASSES`)**, légende, fenêtre d'information, zone de toucher (`stationsSous`)
- `src/filtres.js` : filtres de la couche nitrates (cases par classe, curseur d'année, compteur, réinitialisation)
- `src/style.css` : styles de la page
- `data/` : données géographiques (`departements.geojson`, 96 départements métropolitains, propriétés `code` et `nom`)
- `scripts/fetch_nitrates.py` : mise à jour de `data/nitrates_stations.csv` depuis Hub'Eau
- `scripts/fetch_nitrates_cours_eau.py` : mise à jour de `data/nitrates_cours_eau.csv` depuis Hub'Eau
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
- `data/nitrates_cours_eau.csv` : nitrates dans les eaux de surface (cours d'eau et plans d'eau), API Hub'Eau « Qualité des cours d'eau » v2
  (`/api/v2/qualite_rivieres/analyse_pc` et `station_pc`, paramètre SANDRE 1340), données Naïades, Licence ouverte Etalab 2.0.
  Mêmes colonnes et mêmes règles que `nitrates_stations.csv` (une ligne par station, dernière analyse sur 5 ans), mais `nom` est ici le
  libellé de la station (`libelle_station`) et `code_station` le code Naïades (texte, 8 caractères le plus souvent, parfois 7 ou avec des tirets : `F31-4443`). **Pas encore affichée sur la carte.**
- `data/layers.csv` : catalogue des couches (`id,nom,fichier,type,cle_jointure,colonne_valeur,filtres,palette,unite,source`).
  Documentation seulement : le code ne le lit pas encore, les réglages de la couche sont dans `src/nitrates.js`.
  La colonne `palette` renvoie à `CLASSES` : ne pas y recopier les couleurs.

### Mettre à jour les nitrates

`python3 scripts/fetch_nitrates.py` (Python 3 standard, aucune dépendance ; environ 25 minutes : une requête par département,
l'API est lente). Il réécrit `data/nitrates_stations.csv` et affiche le nombre de stations, celles ignorées et les unités.
Limites de l'API respectées : page de 5000 au plus (max 20000) et profondeur `page × taille` ≤ 20000, d'où le découpage par
département (et par période au-delà de 20000 analyses). La fenêtre est `aujourd'hui − 5 ans`.

### Mettre à jour les nitrates des eaux de surface

`python3 scripts/fetch_nitrates_cours_eau.py` (Python 3 standard, aucune dépendance ; compter plusieurs dizaines de minutes : l'API est lente).
Il réécrit `data/nitrates_cours_eau.csv` et affiche en fin d'exécution les analyses lues, les doublons, le nombre de stations écrites et ignorées
(avec le motif), les unités rencontrées et les stations concernées.

- **API v2 uniquement** (`/api/v2/qualite_rivieres`) : la v1 est fermée. Stations via `station_pc`, analyses via `analyse_pc`, rattachées par
  `code_station`. `analyse_pc` ne donne ni nom, ni commune, ni département : ils viennent de `station_pc`, ainsi que `lat` et `lon`.
- Noms de champs réels (vérifiés par une requête d'une ligne, pas devinés) : `code_parametre` (filtre, `1340`), `code_departement`,
  `date_debut_prelevement` / `date_fin_prelevement` (filtres), `date_prelevement` et `heure_prelevement` (résultat), `resultat`,
  `symbole_unite`, `code_support`, `code_analyse`. Côté stations : `libelle_station`, `libelle_commune`, `code_departement`, `latitude`, `longitude`.
- Limites : page de 5000 au plus (max 20000), profondeur `page × taille` ≤ 20000 : une requête par département (Corse `2A`/`2B` comprise,
  Paris `75` aussi), coupée en deux périodes tant qu'elle dépasse 20000 résultats. Fenêtre : `aujourd'hui − 5 ans`.
- **Doublons** : une même analyse peut apparaître plusieurs fois (même `code_analyse`) : elle n'est comptée qu'une fois. Deux analyses de même
  station, date et heure (fractions différentes) : on garde le `code_analyse` le plus grand ; le script compte les cas où les valeurs diffèrent.
- Seul le support « Eau » (`code_support` = `3`) est retenu ; les autres sont comptés et ignorés.
- **Unité** : une seule attendue, `mg(NO3)/L`. Une station dont la dernière analyse est en `mg/L` (ou autre) n'est **pas écrite** et n'est pas convertie :
  le script la liste. Ne rien convertir sans décision explicite (le facteur dépend de l'espèce chimique exprimée : NO3 ou N).
- Comme pour les eaux souterraines, une station dont la dernière analyse n'a pas de valeur ou de coordonnées est ignorée, sans retomber sur une plus ancienne.
- Classes d'affichage : celles de `CLASSES` dans `src/nitrates.js`, à ne pas recopier.

### Conventions de la couche nitrates

- Cercles MapLibre (`circle`), jamais de marqueurs HTML, sous les étiquettes du fond et au-dessus des départements.
- 5 classes en mg(NO3)/L, alignées sur la limite de qualité de 50 mg/L : ≤ 10, ≤ 25, ≤ 50, ≤ 100, > 100 (la borne haute
  est incluse ; au-dessus de 50, la limite est dépassée).
- **Les classes sont définies une seule fois**, dans `CLASSES` de `src/nitrates.js` (bornes, libellés, couleurs). À son chargement,
  chaque station reçoit `classe` (indice dans `CLASSES`) et `annee` (année de `date_analyse`) ; la couleur des points, la légende
  et les filtres lisent `CLASSES` ou ces propriétés. Ne jamais recopier une borne ou une couleur ailleurs.
- La couleur est `['to-color', ['at', ['get', 'classe'], ['literal', couleurs]]]` : sans `to-color`, MapLibre refuse l'expression
  (« Expected array<color> but found array<string> ») et la couche ne s'affiche pas.
- Une station dont la dernière analyse n'a pas de valeur ou de coordonnées est ignorée (on ne retombe pas sur une analyse plus ancienne).
- Ne jamais mélanger deux unités sans conversion explicite : le script affiche les unités rencontrées, une seule (`mg(NO3)/L`) à ce jour.
- Clic ou toucher sur un point : fenêtre de la station (`.fenetre-station`), et le clic sur un point prime sur celui du département
  (`src/departements.js` l'ignore et ferme sa fenêtre). Même bandeau pleine largeur que les départements sous 560 px.
- Le CSV (≈ 1,9 Mo) est chargé par le navigateur avec `?url` puis converti en GeoJSON ; sa limite de poids visée est ~10 Mo.

### Filtres de la couche nitrates (`src/filtres.js`)

- Bloc « Filtres » (`<details id="filtres">`) au-dessus de la légende : une case par classe (couleur et libellé lus dans `CLASSES`),
  un curseur « Analyses depuis [année] », un compteur « N stations affichées sur 22 518 » et « Réinitialiser ».
- Les filtres passent par `carte.setFilter` sur la couche existante :
  `['all', ['in', ['get', 'classe'], ['literal', [...]]], ['>=', ['get', 'annee'], annee]]`. La source n'est ni rechargée ni recréée,
  et les couches des départements n'ont aucun filtre.
- Années min. et max. du curseur lues dans `date_analyse` (année de la dernière analyse de la station) ; total = stations chargées :
  rien n'est écrit en dur. Le compteur vient d'une table classe × année calculée au chargement.
- Une station filtrée n'est plus dessinée, donc plus cliquable : le clic retombe sur le département. Un point visible prime toujours.

### Lisibilité et toucher

- Rayon dépendant du zoom (1,4 px à z4, 10 px à z14), opacité 0,8, trait blanc fin ; `circle-sort-key` sur la valeur (les plus fortes dessus).
- `stationsSous` (`src/nitrates.js`) cherche les stations dans un carré autour du point : 14 px si le pointeur principal est tactile
  (`pointer: coarse`), 3 px à la souris ; la plus proche gagne (à égalité, la valeur la plus forte). Les départements l'utilisent aussi.

### Panneau, légende et petit écran

- `.panneau` (bas gauche) empile filtres puis légende : ils ne peuvent pas se recouvrir. Il reste au-dessus des crédits, dont la hauteur
  est mesurée par un `ResizeObserver` (variable CSS `--bas-panneau`, `src/main.js`) : 1 ligne à 1280 px, 4 lignes à 390 px.
  Il défile s'il est trop haut et laisse 236 px en haut sous 560 px (fenêtre d'information en bandeau).
- Légende et filtres sont repliés au départ sous 600 px (`PETIT_ECRAN`, `src/nitrates.js`) ; le bandeau d'information garde son seuil de
  560 px (`src/style.css`). Fonds opaques. Sur téléphone, les filtres ouverts couvrent la moitié gauche de la carte : les replier pour toucher un point.

### Thème clair et noms français

- `<meta name="color-scheme" content="only light">` et `:root { color-scheme: only light; }` empêchent l'assombrissement automatique de
  Chrome (« Assombrir les sites Web ») ; chacun suffit, les deux sont gardés. Chrome affiche la valeur calculée `light only`.
  Vérifié avec Chromium 141 en thème sombre et assombrissement forcé (`--enable-features=WebContentsForceDark`, canal `chromium`,
  pas le headless shell) : sans, « De 25 à 50 » devient brun foncé ; avec, rien ne change. Pas testé sur Chrome pour Android.
- `src/main.js` remplace le `text-field` des couches `place` du fond (pays, villes) par `coalesce(name:fr, name)` à `style.load`.
  Non vérifié sur les vraies tuiles OpenFreeMap : sans champ `name:fr`, on retombe sur le nom local.

### Tester la couche nitrates

- Aucune requête réseau : le style OpenFreeMap, les tuiles et les polices sont interceptés par Playwright (style minimal avec des couches `place`).
- Accès à la carte pour les tests : ajouter `;window.__carte = carte;` au `src/main.js` servi par le serveur de développement (`page.route`),
  sans modifier le dépôt. Valeurs attendues calculées à part (module `csv` de Python), jamais avec le code testé.
- Pièges : en développement Vite demande deux fois le CSV (`…csv?import&url` puis les données) ; l'expression `at` du style-spec et
  `createPropertyExpression` (argument `rootKey`) ; ouvrir les filtres sur téléphone avant de compter, et les replier avant de toucher la carte.
