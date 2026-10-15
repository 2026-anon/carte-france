#!/usr/bin/env python3
"""Télécharge la dernière analyse de nitrates de chaque station de cours d'eau et de plan d'eau (France métropolitaine)
depuis l'API Hub'Eau « Qualité des cours d'eau » v2 (données Naïades) et écrit data/nitrates_cours_eau.csv,
avec les mêmes colonnes que data/nitrates_stations.csv.

Usage : python3 scripts/fetch_nitrates_cours_eau.py [--departements 64 09 ...] [--sortie fichier.csv]
Endpoints : /api/v2/qualite_rivieres/station_pc (stations) et /analyse_pc (analyses), rattachées par code_station.
Limites de l'API respectées : taille de page max 20000, profondeur (page × taille) max 20000,
d'où une requête par département, découpée par période au-delà de 20000 résultats.

Règles de sélection, dans cet ordre :
1. Doublons : une même analyse peut revenir plusieurs fois ; elle n'est gardée qu'une fois. Clé : (code_station, code_analyse).
   Le code_analyse seul n'est PAS unique : 39 analyses de stations différentes partagent un même code (deux stations, deux
   dates), et la déduplication sur ce seul champ en supprimait une au hasard de l'ordre des départements.
2. Support : seul « Eau » (code_support 3) est retenu.
3. Qualification : les analyses « Incorrecte » (2) et « Incertaine » (3) sont ignorées AVANT de choisir la dernière analyse
   de chaque station ; « Correcte » (1) et « Non qualifié » (4) sont gardées. Une station dont toutes les analyses sont ignorées
   disparaît (comptée à part).
4. Dernière analyse : la plus récente par (date, heure, code_analyse). Le code_analyse sert à départager deux analyses de même
   date et heure (fractions différentes) : les codes numériques se comparent comme des nombres, les autres comme du texte,
   les numériques avant les textuels (certains codes sont alphanumériques, ex. 01124000202412180835222223B957931340).
5. Une station dont la dernière analyse n'a pas de valeur, ou sans coordonnées, est ignorée : on ne retombe pas sur une plus ancienne.
6. Unité : voir ci-dessous.

Unités. Pour le paramètre 1340 (nitrates), l'unité attendue est mg(NO3)/L. Les analyses en « mg/L » sont traitées comme du
mg(NO3)/L, et la colonne `unite` est écrite « mg(NO3)/L ». Justification (comparaison faite le 2026-10-14, 5 ans de données) :
961 stations ont les deux unités ; sur 736 paires d'analyses à 30 jours ou moins (156 stations, 23 départements dont 141 paires
dans le 64 et 22 dans le 40), le rapport mg/L ÷ mg(NO3)/L a pour médiane 1,00 (quartiles 0,86 à 1,21) ; 71 % des paires sont
entre 0,7 et 1,4 ; seules 6 paires (valeurs très faibles) sont proches de 0,23, le rapport attendu pour de l'azote. Sur 18 paires du
même jour, 17 sont entre 0,7 et 1,4. Les stations passent d'une étiquette à l'autre dans les deux sens (339 de mg(NO3)/L vers mg/L,
529 en sens inverse) : c'est un changement d'étiquette, pas de mesure. LIMITE : le 65, le 09 et le 72 n'ont AUCUNE paire de
comparaison ; pour ces départements la conclusion est une déduction, non une vérification.
Les autres unités (mg(CO3)/L, mg(N)/L…) ne sont pas converties : la station n'est pas écrite et elle est listée à la fin.
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

BASE = 'https://hubeau.eaufrance.fr/api/v2/qualite_rivieres/'
CODE_NITRATES = 1340  # code SANDRE du paramètre « Nitrates »
SUPPORT_EAU = '3'  # code_support : « Eau »
QUALIFICATIONS_IGNOREES = {'2', '3'}  # code_qualification : Incorrecte, Incertaine
UNITE_ECRITE = 'mg(NO3)/L'
UNITES_ACCEPTEES = {'mg(NO3)/L', 'mg/L'}  # mg/L est lu comme mg(NO3)/L (voir l'en-tête)
TAILLE_PAGE = 5000  # page × taille reste sous la profondeur max de 20000
PROFONDEUR_MAX = 20000
CHAMPS_STATION = 'code_station,libelle_station,libelle_commune,code_departement,latitude,longitude'
CHAMPS_ANALYSE = ('code_analyse,code_station,date_prelevement,heure_prelevement,resultat,symbole_unite,'
                  'code_support,code_qualification')
DEPARTEMENTS = [f'{n:02d}' for n in range(1, 96) if n != 20] + ['2A', '2B']  # codes en texte
SORTIE = Path(__file__).resolve().parent.parent / 'data' / 'nitrates_cours_eau.csv'
COLONNES = ['code_station', 'nom', 'lat', 'lon', 'commune', 'code_dept', 'date_analyse', 'valeur', 'unite']


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
    """Toutes les lignes d'une requête, en suivant la pagination."""
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


def cle_code_analyse(code):
    """Clé de départage : numériques comme des nombres, puis les autres comme du texte (ordre total, déterministe)."""
    if code.isascii() and code.isdigit():
        return (0, int(code), '')
    return (1, 0, code)


def cle_analyse(a):
    return (a['date_prelevement'], a['heure_prelevement'] or '', cle_code_analyse(a['code_analyse']))


def selectionner(stations, lignes):
    """Applique les règles de sélection (voir l'en-tête). Renvoie (stations écrites, bilan)."""
    bilan = Counter()
    vues = set()  # (code_station, code_analyse) déjà lus
    dernieres = {}  # code_station -> dernière analyse retenue (valeur absente comprise)
    stations_vues = set()
    for a in lignes:
        bilan['analyses lues'] += 1
        cle_unique = (a['code_station'], a['code_analyse'])
        if cle_unique in vues:
            bilan['doublons (même station et même code_analyse)'] += 1
            continue
        vues.add(cle_unique)
        bilan['qualification ' + str(a['code_qualification'])] += 1
        if a['code_support'] != SUPPORT_EAU:
            bilan['hors support Eau'] += 1
            continue
        stations_vues.add(a['code_station'])
        if a['code_qualification'] in QUALIFICATIONS_IGNOREES:
            bilan['analyses ignorées (Incorrecte ou Incertaine)'] += 1
            continue
        ancienne = dernieres.get(a['code_station'])
        if ancienne is not None and cle_analyse(a)[:2] == cle_analyse(ancienne)[:2]:
            bilan['égalités station + date + heure'] += 1
            if a['resultat'] != ancienne['resultat']:
                bilan['égalités avec des valeurs différentes'] += 1
        if ancienne is None or cle_analyse(a) > cle_analyse(ancienne):
            dernieres[a['code_station']] = a
    bilan['stations avec une analyse'] = len(stations_vues)
    bilan['stations sans analyse retenue (toutes Incorrecte ou Incertaine)'] = len(stations_vues - set(dernieres))

    # On écarte une station si sa dernière analyse est inexploitable, sans retomber sur une plus ancienne.
    ecrites = {}
    for code, a in dernieres.items():
        station = stations.get(code)
        if station is None:
            bilan['ignorée : station absente de station_pc'] += 1
        elif a['resultat'] is None:
            bilan['ignorée : valeur absente'] += 1
        elif station['longitude'] is None or station['latitude'] is None:
            bilan['ignorée : coordonnées manquantes'] += 1
        elif a['symbole_unite'] not in UNITES_ACCEPTEES:
            bilan['ignorée : unité ' + str(a['symbole_unite'])] += 1
        else:
            if a['symbole_unite'] != UNITE_ECRITE:
                bilan['écrite : « mg/L » lu comme mg(NO3)/L'] += 1
            ecrites[code] = {
                'code_station': code,
                'nom': (station['libelle_station'] or '').strip(),
                'lat': round(station['latitude'], 4),
                'lon': round(station['longitude'], 4),
                'commune': station['libelle_commune'] or '',
                'code_dept': station['code_departement'],
                'date_analyse': a['date_prelevement'],
                'valeur': a['resultat'],
                'unite': UNITE_ECRITE,
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
    stations = {}  # code_station -> fiche de la station (station_pc)
    lignes = []
    for dept in args.departements:
        stations.update(stations_du_departement(dept))
        a = analyses(dept, debut, fin)
        lignes += a
        print(f'{dept} : {len(a)} analyses', file=sys.stderr)

    ecrites, bilan = selectionner(stations, lignes)
    ecrire(ecrites, args.sortie)
    print(f'depuis {debut} : {args.sortie}', file=sys.stderr)
    for motif, n in sorted(bilan.items()):
        print(f'{motif} : {n}', file=sys.stderr)


if __name__ == '__main__':
    main()
