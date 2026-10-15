# Données du réseau ferré national (`rfn_lignes.geojson`, `rfn_gares.geojson`, `rfn_meta.json`)

Ces fichiers sont des **bases de données dérivées** de jeux ouverts de SNCF Réseau et de SNCF Gares & Connexions, publiés sur
<https://ressources.data.sncf.com> sous licence **Open Database License (ODbL) 1.0** (<https://opendatacommons.org/licenses/odbl/1-0/>).

- **Attribution** : « SNCF Réseau » et « SNCF Gares & Connexions », avec un lien vers la source (voir `rfn_meta.json` pour les jeux, leurs dates
  et leurs licences) ; elle figure dans les crédits de la carte.
- **Partage à l'identique** : ces fichiers, qui adaptent les données (rattachement des attributs, simplification des tracés, arrondi des
  coordonnées), sont redistribués sous la même licence ODbL.
- Ils sont produits par `scripts/preparer_rfn.py` ; les règles de classement et les écarts avec la légende officielle sont décrits dans `CLAUDE.md`.
- Usage informatif seulement : ni navigation ni exploitation ferroviaire (réserve reprise des descriptions des jeux d'origine).
