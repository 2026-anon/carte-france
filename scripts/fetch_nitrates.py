#!/usr/bin/env python3
"""Télécharge la dernière analyse de nitrates de chaque station (eaux souterraines, France métropolitaine)
depuis l'API Hub'Eau « Qualité des nappes d'eau souterraine » et écrit data/nitrates_stations.csv.

Usage : python3 scripts/fetch_nitrates.py
Limites de l'API respectées : taille de page max 20000, profondeur (page × taille) max 20000,
d'où une requête par département, découpée par année si un département dépasse 20000 analyses.
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

URL = 'https://hubeau.eaufrance.fr/api/v1/qualite_nappes/analyses'
CODE_NITRATES = 1340
TAILLE_PAGE = 5000  # défaut de l'API ; page × taille reste sous la profondeur max de 20000
PROFONDEUR_MAX = 20000
CHAMPS = ('bss_id,code_bss,longitude,latitude,nom_commune_actuel,num_departement,'
          'date_debut_prelevement,resultat,symbole_unite')
DEPARTEMENTS = [f'{n:02d}' for n in range(1, 96) if n != 20] + ['2A', '2B']  # codes en texte
SORTIE = Path(__file__).resolve().parent.parent / 'data' / 'nitrates_stations.csv'


def aujourd_hui_moins_5_ans():
    auj = date.today()
    try:
        return auj.replace(year=auj.year - 5)
    except ValueError:  # 29 février
        return auj.replace(year=auj.year - 5, day=28)


def requete(params):
    url = URL + '?' + urllib.parse.urlencode(params)
    for essai in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as rep:
                return json.load(rep)
        except Exception as e:  # réseau ou erreur serveur : on réessaie avec attente croissante
            if essai == 4:
                raise
            print(f'  nouvel essai ({e})', file=sys.stderr)
            time.sleep(2 ** (essai + 1))


def analyses(dept, debut, fin):
    """Toutes les analyses de nitrates d'un département entre deux dates (incluses), triées de la plus récente à la plus ancienne."""
    params = {'code_param': CODE_NITRATES, 'num_departement': dept, 'date_debut_prelevement': debut,
              'date_fin_prelevement': fin, 'fields': CHAMPS, 'sort': 'desc', 'size': TAILLE_PAGE}
    premiere = requete({**params, 'page': 1})
    total = premiere['count']
    if total > PROFONDEUR_MAX:
        # trop d'analyses pour la profondeur d'accès : on coupe la période en deux
        d1, d2 = date.fromisoformat(debut), date.fromisoformat(fin)
        milieu = d1 + (d2 - d1) / 2
        return (analyses(dept, (milieu + date.resolution).isoformat(), fin)
                + analyses(dept, debut, milieu.isoformat()))
    donnees = premiere['data']
    page = 2
    while len(donnees) < total:
        time.sleep(0.2)
        donnees += requete({**params, 'page': page})['data']
        page += 1
    return donnees


def main():
    debut = aujourd_hui_moins_5_ans().isoformat()
    fin = date.today().isoformat()
    dernieres = {}  # code_station -> dernière analyse (valeur absente comprise)
    total = 0
    for dept in DEPARTEMENTS:
        lignes = analyses(dept, debut, fin)
        total += len(lignes)
        print(f'{dept} : {len(lignes)} analyses', file=sys.stderr)
        for a in lignes:
            ancienne = dernieres.get(a['bss_id'])
            if ancienne is None or a['date_debut_prelevement'] > ancienne['date_debut_prelevement']:
                dernieres[a['bss_id']] = a

    # On écarte une station si sa dernière analyse est inexploitable, sans retomber sur une plus ancienne.
    stations = {}
    ignorees = Counter()
    for code, a in dernieres.items():
        if a['resultat'] is None:
            ignorees['valeur absente'] += 1
        elif a['longitude'] is None or a['latitude'] is None:
            ignorees['coordonnées manquantes'] += 1
        else:
            stations[code] = {
                'code_station': code,
                'nom': a['code_bss'],
                'lat': round(a['latitude'], 4),
                'lon': round(a['longitude'], 4),
                'commune': a['nom_commune_actuel'] or '',
                'code_dept': a['num_departement'],
                'date_analyse': a['date_debut_prelevement'][:10],
                'valeur': a['resultat'],
                'unite': a['symbole_unite'] or '',
            }
    with open(SORTIE, 'w', newline='', encoding='utf-8') as f:
        champs = ['code_station', 'nom', 'lat', 'lon', 'commune', 'code_dept', 'date_analyse', 'valeur', 'unite']
        w = csv.DictWriter(f, fieldnames=champs, lineterminator='\n')
        w.writeheader()
        for s in sorted(stations.values(), key=lambda s: s['code_station']):
            w.writerow(s)
    print(f'{total} analyses lues depuis {debut}, {len(dernieres)} stations, {len(stations)} écrites dans {SORTIE}', file=sys.stderr)
    for motif, n in ignorees.items():
        print(f'stations ignorées ({motif}) : {n}', file=sys.stderr)
    print('unités :', dict(Counter(s['unite'] for s in stations.values())), file=sys.stderr)


if __name__ == '__main__':
    main()
