#!/usr/bin/env python3
"""Télécharge la dernière analyse de nitrates de chaque station de cours d'eau et de plan d'eau (France métropolitaine)
depuis l'API Hub'Eau « Qualité des cours d'eau » v2 (données Naïades) et écrit data/nitrates_cours_eau.csv,
avec les mêmes colonnes que data/nitrates_stations.csv.

Usage : python3 scripts/fetch_nitrates_cours_eau.py
Endpoints : /api/v2/qualite_rivieres/station_pc (stations) et /analyse_pc (analyses), rattachées par code_station.
Limites de l'API respectées : taille de page max 20000, profondeur (page × taille) max 20000,
d'où une requête par département, découpée par période au-delà de 20000 résultats.
Une seule unité est attendue (mg(NO3)/L) : une station dont la dernière analyse est dans une autre unité n'est pas écrite,
elle est listée à la fin (aucune conversion silencieuse).
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

BASE = 'https://hubeau.eaufrance.fr/api/v2/qualite_rivieres/'
CODE_NITRATES = 1340  # code SANDRE du paramètre « Nitrates »
SUPPORT_EAU = '3'  # code_support : « Eau »
UNITE_ATTENDUE = 'mg(NO3)/L'
TAILLE_PAGE = 5000  # page × taille reste sous la profondeur max de 20000
PROFONDEUR_MAX = 20000
CHAMPS_STATION = 'code_station,libelle_station,libelle_commune,code_departement,latitude,longitude'
CHAMPS_ANALYSE = 'code_analyse,code_station,date_prelevement,heure_prelevement,resultat,symbole_unite,code_support'
DEPARTEMENTS = [f'{n:02d}' for n in range(1, 96) if n != 20] + ['2A', '2B']  # codes en texte
SORTIE = Path(__file__).resolve().parent.parent / 'data' / 'nitrates_cours_eau.csv'


def aujourd_hui_moins_5_ans():
    auj = date.today()
    try:
        return auj.replace(year=auj.year - 5)
    except ValueError:  # 29 février
        return auj.replace(year=auj.year - 5, day=28)


def requete(endpoint, params):
    url = BASE + endpoint + '?' + urllib.parse.urlencode(params)
    for essai in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as rep:
                return json.load(rep)
        except Exception as e:  # réseau ou erreur serveur : on réessaie avec attente croissante
            if essai == 4:
                raise
            print(f'  nouvel essai ({e})', file=sys.stderr)
            time.sleep(2 ** (essai + 1))


def toutes_les_pages(endpoint, params):
    """Toutes les lignes d'une requête, en suivant la pagination ; le nombre total est vérifié."""
    premiere = requete(endpoint, {**params, 'size': TAILLE_PAGE, 'page': 1})
    total = premiere['count']
    donnees = premiere['data']
    page = 2
    while len(donnees) < total:
        time.sleep(0.2)
        donnees += requete(endpoint, {**params, 'size': TAILLE_PAGE, 'page': page})['data']
        page += 1
    return total, donnees


def stations_du_departement(dept):
    total, lignes = toutes_les_pages('station_pc', {'code_departement': dept, 'fields': CHAMPS_STATION})
    if total > PROFONDEUR_MAX:
        raise SystemExit(f'{dept} : {total} stations, au-delà de la profondeur d’accès de l’API')
    return {s['code_station']: s for s in lignes}


def analyses(dept, debut, fin):
    """Toutes les analyses de nitrates d'un département entre deux dates (incluses)."""
    params = {'code_parametre': CODE_NITRATES, 'code_departement': dept, 'date_debut_prelevement': debut,
              'date_fin_prelevement': fin, 'fields': CHAMPS_ANALYSE, 'sort': 'desc'}
    premiere = requete('analyse_pc', {**params, 'size': TAILLE_PAGE, 'page': 1})
    if premiere['count'] > PROFONDEUR_MAX:
        # trop de résultats pour la profondeur d'accès : on coupe la période en deux
        d1, d2 = date.fromisoformat(debut), date.fromisoformat(fin)
        if d1 == d2:
            raise SystemExit(f'{dept} : plus de {PROFONDEUR_MAX} analyses le {debut}')
        milieu = d1 + (d2 - d1) / 2
        return (analyses(dept, (milieu + date.resolution).isoformat(), fin)
                + analyses(dept, debut, milieu.isoformat()))
    return toutes_les_pages('analyse_pc', params)[1]


def main():
    debut = aujourd_hui_moins_5_ans().isoformat()
    fin = date.today().isoformat()
    stations = {}  # code_station -> fiche de la station (station_pc)
    dernieres = {}  # code_station -> dernière analyse (valeur absente comprise)
    vues = set()  # code_analyse déjà lus : une même analyse peut revenir plusieurs fois
    lues = doublons = hors_eau = departement_vide = 0
    egalites = 0  # analyses de même station, date et heure (fractions différentes) : on garde la plus grande valeur d'identifiant
    egalites_differentes = 0
    for dept in DEPARTEMENTS:
        stations.update(stations_du_departement(dept))
        lignes = analyses(dept, debut, fin)
        lues += len(lignes)
        print(f'{dept} : {len(lignes)} analyses', file=sys.stderr)
        for a in lignes:
            if a['code_analyse'] in vues:
                doublons += 1
                continue
            vues.add(a['code_analyse'])
            if a['code_support'] != SUPPORT_EAU:
                hors_eau += 1
                continue
            cle = (a['date_prelevement'], a['heure_prelevement'] or '')
            ancienne = dernieres.get(a['code_station'])
            if ancienne is not None:
                cle_ancienne = (ancienne['date_prelevement'], ancienne['heure_prelevement'] or '')
                if cle == cle_ancienne:
                    egalites += 1
                    if a['resultat'] != ancienne['resultat'] or a['symbole_unite'] != ancienne['symbole_unite']:
                        egalites_differentes += 1
                    if int(a['code_analyse']) > int(ancienne['code_analyse']):
                        dernieres[a['code_station']] = a
                elif cle > cle_ancienne:
                    dernieres[a['code_station']] = a
            else:
                dernieres[a['code_station']] = a

    # On écarte une station si sa dernière analyse est inexploitable, sans retomber sur une plus ancienne.
    ecrites = {}
    ignorees = Counter()
    autres_unites = {}  # unité -> codes des stations concernées
    for code, a in dernieres.items():
        station = stations.get(code)
        if station is None:
            ignorees['station absente de station_pc'] += 1
        elif a['resultat'] is None:
            ignorees['valeur absente'] += 1
        elif station['longitude'] is None or station['latitude'] is None:
            ignorees['coordonnées manquantes'] += 1
        elif a['symbole_unite'] != UNITE_ATTENDUE:
            ignorees['unité autre que ' + UNITE_ATTENDUE] += 1
            autres_unites.setdefault(a['symbole_unite'], []).append(code)
        else:
            ecrites[code] = {
                'code_station': code,
                'nom': (station['libelle_station'] or '').strip(),
                'lat': round(station['latitude'], 4),
                'lon': round(station['longitude'], 4),
                'commune': station['libelle_commune'] or '',
                'code_dept': station['code_departement'],
                'date_analyse': a['date_prelevement'],
                'valeur': a['resultat'],
                'unite': a['symbole_unite'],
            }
    with open(SORTIE, 'w', newline='', encoding='utf-8') as f:
        champs = ['code_station', 'nom', 'lat', 'lon', 'commune', 'code_dept', 'date_analyse', 'valeur', 'unite']
        w = csv.DictWriter(f, fieldnames=champs, lineterminator='\n')
        w.writeheader()
        for s in sorted(ecrites.values(), key=lambda s: s['code_station']):
            w.writerow(s)
    print(f'{lues} analyses lues depuis {debut} ({doublons} doublons de code_analyse, {hors_eau} hors support Eau), '
          f'{len(dernieres)} stations, {len(ecrites)} écrites dans {SORTIE}', file=sys.stderr)
    print(f'égalités station + date + heure : {egalites} (dont {egalites_differentes} avec des valeurs différentes)', file=sys.stderr)
    for motif, n in ignorees.items():
        print(f'stations ignorées ({motif}) : {n}', file=sys.stderr)
    for unite, codes in autres_unites.items():
        print(f'unité « {unite} » : {len(codes)} stations non écrites, ex. {", ".join(sorted(codes)[:5])}', file=sys.stderr)
    print('unités écrites :', dict(Counter(s['unite'] for s in ecrites.values())), file=sys.stderr)


if __name__ == '__main__':
    main()
