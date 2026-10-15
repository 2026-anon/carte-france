#!/usr/bin/env python3
"""Télécharge la dernière analyse de nitrates de chaque station (eaux souterraines, France métropolitaine)
depuis l'API Hub'Eau « Qualité des nappes d'eau souterraine » et écrit data/nitrates_stations.csv.

Usage : python3 scripts/fetch_nitrates.py [--departements 11 2A ...] [--sortie fichier.csv]
Limites de l'API respectées : taille de page max 20000, profondeur (page × taille) max 20000,
d'où une requête par département, découpée par année si un département dépasse 20000 analyses.

Règles de sélection (les mêmes qu'avec scripts/fetch_nitrates_cours_eau.py pour la qualification) :
1. Qualification : les analyses « Incorrecte » (code_qualification 2) et « Incertaine » (3) sont ignorées AVANT de choisir la
   dernière analyse de chaque station ; « Correcte » (1), « Non qualifié » (4) et le code 0 (« non définissable ») sont gardées.
   Une station dont toutes les analyses sont ignorées disparaît (comptée à part).
2. Dernière analyse : le plus grand horodatage date_debut_prelevement. À horodatage identique (fractions différentes), on garde
   la valeur la plus élevée (une valeur absente passe après toute valeur), puis à valeur égale l'unité par ordre alphabétique :
   l'ordre est total, donc deux exécutions donnent le même CSV, quel que soit l'ordre de réception des lignes par l'API.
3. Une station dont la dernière analyse n'a pas de valeur, ou sans coordonnées, est ignorée : on ne retombe pas sur une plus ancienne.
"""
import argparse
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
QUALIFICATIONS_IGNOREES = {'2', '3'}  # code_qualification : Incorrecte, Incertaine
CHAMPS = ('bss_id,code_bss,longitude,latitude,nom_commune_actuel,num_departement,'
          'date_debut_prelevement,resultat,symbole_unite,code_qualification')
DEPARTEMENTS = [f'{n:02d}' for n in range(1, 96) if n != 20] + ['2A', '2B']  # codes en texte
SORTIE = Path(__file__).resolve().parent.parent / 'data' / 'nitrates_stations.csv'
COLONNES = ['code_station', 'nom', 'lat', 'lon', 'commune', 'code_dept', 'date_analyse', 'valeur', 'unite']


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


def cle_analyse(a):
    """Clé de « dernière analyse » : horodatage, puis valeur la plus élevée (absente en dernier), puis unité."""
    valeur = a['resultat']
    return (a['date_debut_prelevement'], valeur is not None, valeur if valeur is not None else 0, a['symbole_unite'] or '')


def selectionner(lignes):
    """Applique les règles de sélection (voir l'en-tête). Renvoie (stations écrites, bilan)."""
    bilan = Counter()
    dernieres = {}  # code_station -> dernière analyse retenue (valeur absente comprise)
    stations_vues = set()
    for a in lignes:
        bilan['analyses lues'] += 1
        bilan['qualification ' + str(a['code_qualification'])] += 1
        stations_vues.add(a['bss_id'])
        if a['code_qualification'] in QUALIFICATIONS_IGNOREES:
            bilan['analyses ignorées (Incorrecte ou Incertaine)'] += 1
            continue
        ancienne = dernieres.get(a['bss_id'])
        if ancienne is not None and a['date_debut_prelevement'] == ancienne['date_debut_prelevement']:
            bilan['égalités station + horodatage'] += 1
            if a['resultat'] != ancienne['resultat']:
                bilan['égalités avec des valeurs différentes'] += 1
        if ancienne is None or cle_analyse(a) > cle_analyse(ancienne):
            dernieres[a['bss_id']] = a
    bilan['stations avec une analyse'] = len(stations_vues)
    bilan['stations sans analyse retenue (toutes Incorrecte ou Incertaine)'] = len(stations_vues - set(dernieres))

    # On écarte une station si sa dernière analyse est inexploitable, sans retomber sur une plus ancienne.
    ecrites = {}
    for code, a in dernieres.items():
        if a['resultat'] is None:
            bilan['ignorée : valeur absente'] += 1
        elif a['longitude'] is None or a['latitude'] is None:
            bilan['ignorée : coordonnées manquantes'] += 1
        else:
            ecrites[code] = {
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
    bilan['stations écrites'] = len(ecrites)
    return ecrites, bilan


def ecrire(ecrites, sortie):
    with open(sortie, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLONNES, lineterminator='\n')
        w.writeheader()
        for s in sorted(ecrites.values(), key=lambda s: s['code_station']):
            w.writerow(s)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--departements', nargs='+', default=DEPARTEMENTS, help='codes de départements (texte), tous par défaut')
    parser.add_argument('--sortie', type=Path, default=SORTIE, help='fichier CSV à écrire')
    args = parser.parse_args()

    debut = aujourd_hui_moins_5_ans().isoformat()
    fin = date.today().isoformat()
    lignes = []
    for dept in args.departements:
        a = analyses(dept, debut, fin)
        lignes += a
        print(f'{dept} : {len(a)} analyses', file=sys.stderr)

    ecrites, bilan = selectionner(lignes)
    ecrire(ecrites, args.sortie)
    print(f'depuis {debut} : {args.sortie}', file=sys.stderr)
    for motif, n in sorted(bilan.items()):
        print(f'{motif} : {n}', file=sys.stderr)
    print('unités :', dict(Counter(s['unite'] for s in ecrites.values())), file=sys.stderr)


if __name__ == '__main__':
    main()
