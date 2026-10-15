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
- `src/nitrates.js` : couches de nitrates (cercles) : **définition des classes (`CLASSES`)** et **des couches (`COUCHES`, une configuration par couche)**,
  chargement des CSV, légende, fenêtre d'information, zone de toucher (`stationsSous`, `couchesVisibles`)
- `src/filtres.js` : filtres des couches de nitrates (cases par classe, curseur d'année, un compteur par couche, réinitialisation)
- `src/couches.js` : bloc « Couches » (une case par couche pour l'afficher ou la masquer)
- `src/dom.js` : `creer(balise, classe, texte)`, pour construire les blocs sans HTML interprété
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
  libellé de la station (`libelle_station`) et `code_station` le code Naïades (texte, 8 caractères le plus souvent, parfois 7 ou avec des tirets : `F31-4443`). Affichée sur la carte (couche `nitrates_eaux_surface`). `unite` vaut toujours `mg(NO3)/L` (voir « Unité » ci-dessous).
- `data/layers.csv` : catalogue des couches (`id,nom,fichier,type,cle_jointure,colonne_valeur,filtres,palette,unite,source`).
  Documentation seulement : le code ne le lit pas encore, les réglages des couches sont dans `COUCHES` (`src/nitrates.js`), dont l'`id`
  est celui du catalogue. La colonne `palette` renvoie à `CLASSES` : ne pas y recopier les couleurs.

### Mettre à jour les nitrates

`python3 scripts/fetch_nitrates.py` (Python 3 standard, aucune dépendance ; environ 25 minutes : une requête par département,
l'API est lente). Il réécrit `data/nitrates_stations.csv` et affiche le nombre de stations, celles ignorées et les unités.
Limites de l'API respectées : page de 5000 au plus (max 20000) et profondeur `page × taille` ≤ 20000, d'où le découpage par
département (et par période au-delà de 20000 analyses). La fenêtre est `aujourd'hui − 5 ans`.

### Mettre à jour les nitrates des eaux de surface

`python3 scripts/fetch_nitrates_cours_eau.py` (Python 3 standard, aucune dépendance ; compter plusieurs dizaines de minutes : l'API est lente).
Il réécrit `data/nitrates_cours_eau.csv` et affiche en fin d'exécution un bilan : analyses lues, doublons, qualifications, stations écrites et ignorées
(avec le motif), unités rencontrées.

- **API v2 uniquement** (`/api/v2/qualite_rivieres`) : la v1 est fermée. Stations via `station_pc`, analyses via `analyse_pc`, rattachées par
  `code_station`. `analyse_pc` ne donne ni nom, ni commune, ni département : ils viennent de `station_pc`, ainsi que `lat` et `lon`.
- Noms de champs réels (vérifiés par une requête d'une ligne, pas devinés) : `code_parametre` (filtre, `1340`), `code_departement`,
  `date_debut_prelevement` / `date_fin_prelevement` (filtres), `date_prelevement` et `heure_prelevement` (résultat), `resultat`,
  `symbole_unite`, `code_support`, `code_qualification`, `code_analyse`. Côté stations : `libelle_station`, `libelle_commune`, `code_departement`, `latitude`, `longitude`.
- Limites : page de 5000 au plus (max 20000), profondeur `page × taille` ≤ 20000 : une requête par département (Corse `2A`/`2B` comprise,
  Paris `75` aussi), coupée en deux périodes tant qu'elle dépasse 20000 résultats. Fenêtre : `aujourd'hui − 5 ans`.
- **Doublons** : une même analyse peut apparaître plusieurs fois ; clé de déduplication `(code_station, code_analyse)`. **Ne jamais dédupliquer sur
  `code_analyse` seul** : il n'est pas unique (37 analyses de stations différentes en partageaient un ; la première version en supprimait une au hasard
  de l'ordre des départements, ce qui a faussé la valeur de 11 stations). Deux analyses de même station, date et heure (fractions différentes) :
  on garde la plus grande clé `code_analyse`, les codes numériques se comparant comme des nombres, les autres (alphanumériques) comme du texte,
  numériques d'abord. Le script compte les égalités dont les valeurs diffèrent.
- Seul le support « Eau » (`code_support` = `3`) est retenu ; les autres sont comptés et ignorés.
- **Qualification** : les analyses « Incorrecte » (`code_qualification` 2) et « Incertaine » (3) sont ignorées **avant** de choisir la dernière analyse
  de chaque station ; « Correcte » (1) et « Non qualifié » (4) sont gardées. Sur 261 948 analyses uniques : 257 242 Correcte, 4 297 Non qualifié,
  408 Incertaine, 0 Incorrecte, 1 de code 0. Effet mesuré : 0 station ne disparaît, 1 apparaît (sa dernière analyse, sans valeur et Incertaine, est écartée),
  58 changent de valeur, 57 de date, 25 de classe. Contrairement à cette couche, `scripts/fetch_nitrates.py` (eaux souterraines) ne lit pas la qualification.
- **Unité** : l'unité attendue pour 1340 est `mg(NO3)/L`. Les analyses en `mg/L` sont **lues comme du `mg(NO3)/L`** (1 779 stations) et la colonne `unite`
  est écrite `mg(NO3)/L`. Justification chiffrée (comparée le 2026-10-14) : 961 stations ont les deux unités ; sur 736 paires à 30 jours ou moins
  (156 stations, 23 départements, dont 141 paires dans le 64 et 22 dans le 40) le rapport `mg/L` ÷ `mg(NO3)/L` a pour médiane 1,00 (quartiles 0,86 à 1,21),
  71 % des paires sont entre 0,7 et 1,4, et 6 seulement (valeurs très faibles) proches de 0,23, le rapport d'un azote ; les stations changent d'étiquette
  dans les deux sens (339 de `mg(NO3)/L` vers `mg/L`, 529 l'inverse). **Limite : le 65, le 09 et le 72 n'ont aucune paire de comparaison** : pour eux,
  c'est une déduction, pas une vérification. Les autres unités (`mg(CO3)/L`, `mg(N)/L`) ne sont **pas converties** : leur station n'est pas écrite et
  le script la compte.
- Comme pour les eaux souterraines, une station dont la dernière analyse n'a pas de valeur ou de coordonnées est ignorée, sans retomber sur une plus ancienne.
- **Valeurs extrêmes examinées et conservées** : les 7 stations au-dessus de 100 mg(NO3)/L ont été passées en revue (série complète, statut, qualification),
  aucune n'est retirée. Thiéloup à Mesnil-Saint-Père (140, contre 2,5 à 19 avant), Canal du Midi à Villepinte (102, médiane 1,7) et Ségrassiés à
  Pampelonne (193, une seule autre analyse à 46) restent douteuses mais non prouvées fausses. Préfontaines (118), Plauzat (110), Toucy (110, pic d'automne
  qui se répète) et la Jorle à Sénestis (130, série de 96 à 144 ; ses analyses alternent `mg/L` et `mg(NO3)/L` avec des valeurs concordantes) sont cohérentes
  avec leur historique. La Verdonnelle (123, Incertaine) n'y figure plus : le filtre de qualification la ramène à 31,4 (2026-03-10).
- Pour tester le script sans tout télécharger : `python3 scripts/fetch_nitrates_cours_eau.py --departements 61 2A 64 --sortie /tmp/test.csv`, puis comparer
  aux lignes du CSV de ces départements (le 61 et la 2A ont un `code_analyse` en commun : cas de test de la déduplication).
- Classes d'affichage : celles de `CLASSES` dans `src/nitrates.js`, à ne pas recopier.

### Conventions des couches de nitrates

- Cercles MapLibre (`circle`), jamais de marqueurs HTML, sous les étiquettes du fond et au-dessus des départements.
- 5 classes en mg(NO3)/L, alignées sur la limite de qualité de 50 mg/L : ≤ 10, ≤ 25, ≤ 50, ≤ 100, > 100 (la borne haute
  est incluse ; au-dessus de 50, la limite est dépassée).
- **Les classes sont définies une seule fois**, dans `CLASSES` de `src/nitrates.js` (bornes, libellés, couleurs), et **partagées par toutes les couches**
  pour qu'elles soient comparables. À son chargement, chaque station reçoit `classe` (indice dans `CLASSES`) et `annee` (année de `date_analyse`) ;
  la couleur des points, la légende et les filtres lisent `CLASSES` ou ces propriétés. Ne jamais recopier une borne ou une couleur ailleurs.
- **Une configuration par couche**, dans `COUCHES` (`src/nitrates.js`) : `id` (celui du catalogue `data/layers.csv`, aussi identifiant de la source et de la couche
  MapLibre), `nom` (bloc des couches, compteurs, légende), `libelleFenetre` (type affiché dans la fenêtre), `fichier` (CSV importé avec `?url`),
  `contour` (`couleur`, `largeur` en pixels aux zooms 4 et 8, `description` pour la légende), `attribution`. Ajouter une couche = une entrée, son CSV et sa ligne
  de catalogue : le chargement, la légende, les filtres, le bloc des couches et la fenêtre la lisent. L'ordre est celui du dessin (la dernière est au-dessus).
- **Le remplissage dit la classe, le contour dit la couche** : trait blanc fin pour les eaux souterraines (0,2 puis 0,7 px), contour bleu foncé plus épais
  pour les eaux de surface (0,2 puis 1,1 px ; plus épais à bas zoom, il noyait les couleurs). La légende affiche ces deux symboles, lus dans la configuration.
- La couleur est `['to-color', ['at', ['get', 'classe'], ['literal', couleurs]]]` : sans `to-color`, MapLibre refuse l'expression
  (« Expected array<color> but found array<string> ») et la couche ne s'affiche pas.
- Une station dont la dernière analyse n'a pas de valeur ou de coordonnées est ignorée (on ne retombe pas sur une analyse plus ancienne).
- Ne jamais mélanger deux unités sans conversion explicite : le script affiche les unités rencontrées, une seule (`mg(NO3)/L`) à ce jour.
- Clic ou toucher sur un point d'une couche visible : une seule fenêtre pour toutes les couches (`.fenetre-station`), avec en tête le type de la couche
  (`libelleFenetre`), puis nom, commune, valeur, date et code. Le clic sur un point prime sur celui du département (`src/departements.js` l'ignore et ferme sa
  fenêtre). Même bandeau pleine largeur que les départements sous 560 px, et elle passe au-dessus du panneau (`z-index`) : celle d'une station de surface
  (nom long sur deux lignes) peut faire 182 px de haut et dépasser la place réservée en haut.
- Les CSV (≈ 1,9 Mo et 1,2 Mo) sont chargés en parallèle par le navigateur avec `?url`, puis convertis en GeoJSON ; limite de poids visée : ~10 Mo par fichier.
- Crédits : une attribution par source (ADES, Naïades, avec la licence). MapLibre n'affiche que celles des couches visibles ; la mise à jour suit le rendu
  (≈ 220 ms, jusqu'à 400 ms mesurés en rendu logiciel). Avec les deux, les crédits font 5 lignes à 390 px et 2 lignes à 1280 px.

### Couches et filtres (`src/couches.js`, `src/filtres.js`)

- Bloc « Couches » (`<details id="couches">`) : une case par couche (avec son symbole de contour) ; décochée, la couche passe en `visibility: none` (la source reste
  chargée). Une couche masquée n'est ni dessinée ni cliquable (`couchesVisibles` l'exclut de `stationsSous`), son compteur et son crédit disparaissent.
  Si aucune couche n'est affichée, le compteur dit « Aucune couche affichée. ».
- Bloc « Filtres » (`<details id="filtres">`) : une case par classe (couleur et libellé lus dans `CLASSES`), un curseur « Analyses depuis [année] »,
  un compteur par couche visible (« Eaux souterraines : N stations affichées sur M ») et « Réinitialiser » (les filtres seulement, pas les couches).
- **Les mêmes filtres s'appliquent à toutes les couches** : `carte.setFilter` sur chacune, y compris une couche masquée (réaffichée, elle est déjà filtrée) :
  `['all', ['in', ['get', 'classe'], ['literal', [...]]], ['>=', ['get', 'annee'], annee]]`. Les sources ne sont ni rechargées ni recréées,
  et les couches des départements n'ont aucun filtre.
- Années min. et max. du curseur lues dans `date_analyse` des deux CSV (année de la dernière analyse de la station) ; M = stations chargées de chaque couche :
  rien n'est écrit en dur. Les compteurs viennent d'une table couche × classe × année calculée au chargement.
- Une station filtrée n'est plus dessinée, donc plus cliquable : le clic retombe sur le département. Un point visible prime toujours.

### Lisibilité et toucher

- Rayon dépendant du zoom (1,4 px à z4, 10 px à z14), opacité 0,8, trait blanc fin ; `circle-sort-key` sur la valeur (les plus fortes dessus).
- `stationsSous` (`src/nitrates.js`) cherche les stations des **couches visibles** dans un carré autour du point : 14 px si le pointeur principal est tactile
  (`pointer: coarse`), 3 px à la souris ; la plus proche gagne, quelle que soit la couche (à égalité, la valeur la plus forte). Les départements l'utilisent aussi.
  Chaque couche a sa propre `circle-sort-key` : l'ordre de dessin entre deux couches est celui de `COUCHES`, pas la valeur.

### Panneau, légende et petit écran

- `.panneau` (bas gauche) empile couches, filtres puis légende : ils ne peuvent pas se recouvrir. Il reste au-dessus des crédits, dont la hauteur
  est mesurée par un `ResizeObserver` (variable CSS `--bas-panneau`, `src/main.js`). Il défile s'il est trop haut et laisse 72 px en haut sur ordinateur,
  236 px sous 560 px (fenêtre d'information en bandeau).
- Couches, filtres et légende sont repliés au départ sous 600 px (`PETIT_ECRAN`, `src/nitrates.js`) ; le bandeau d'information garde son seuil de
  560 px (`src/style.css`). Fonds opaques. Sur téléphone, les blocs ouverts couvrent la moitié gauche de la carte : les replier pour toucher un point.
- Place : à 1280×800, les trois blocs ouverts tiennent sans défilement (662 px de contenu ; marges et hauteurs de ligne resserrées pour cela, légende sur une ligne).
  À 390×844 (486 px de place), couches ouvertes seules (233 px) ou légende ouverte seule (329 px) tiennent ; filtres ouverts, comme les trois blocs ensemble,
  le panneau défile (rien n'est coupé : tout reste atteignable en le faisant défiler).

### Thème clair et noms français

- `<meta name="color-scheme" content="only light">` et `:root { color-scheme: only light; }` empêchent l'assombrissement automatique de
  Chrome (« Assombrir les sites Web ») ; chacun suffit, les deux sont gardés. Chrome affiche la valeur calculée `light only`.
  Vérifié avec Chromium 141 en thème sombre et assombrissement forcé (`--enable-features=WebContentsForceDark`, canal `chromium`,
  pas le headless shell) : sans, « De 25 à 50 » devient brun foncé ; avec, rien ne change. Pas testé sur Chrome pour Android.
- `src/main.js` remplace le `text-field` des couches `place` du fond (pays, villes) par `coalesce(name:fr, name)` à `style.load`.
  Non vérifié sur les vraies tuiles OpenFreeMap : sans champ `name:fr`, on retombe sur le nom local.

### Tester la couche nitrates

- Aucune requête réseau : le style OpenFreeMap, les tuiles et les polices sont interceptés par Playwright (style minimal avec des couches `place`
  et une attribution calquée sur celle d'OpenFreeMap, pour mesurer la hauteur réelle des crédits).
- Accès à la carte pour les tests : ajouter `;window.__carte = carte;` au `src/main.js` servi par le serveur de développement (`page.route`),
  sans modifier le dépôt. Valeurs attendues calculées à part (module `csv` de Python), jamais avec le code testé.
- Pièges : en développement Vite demande deux fois chaque CSV (`…csv?import&url` puis les données) ; l'expression `at` du style-spec et
  `createPropertyExpression` (argument `rootKey`) ; ouvrir les filtres sur téléphone avant de compter, et les replier avant de toucher la carte ;
  attendre une condition (`waitForFunction`) et non un délai fixe pour les crédits, qui suivent le rendu.
- Comparer la couche des eaux souterraines à `main` (copie par `git archive` servie sur un autre port) : mêmes propriétés de dessin, mêmes stations avec toutes leurs
  propriétés, rendu identique pixel à pixel (carte seule, sans panneau ni contrôles).
- Tester `stationsSous` (égalité de distance, couche masquée) avec une fausse carte : `await import('/src/nitrates.js')` dans la page de développement renvoie
  le module déjà chargé par l'application.
