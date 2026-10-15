#!/usr/bin/env python3
"""Prépare les données du réseau ferré national (lignes et gares) pour la carte.

Usage : python3 scripts/preparer_rfn.py [--brut dossier] [--telecharger]
Dépendance : numpy (pip install numpy). Le reste est la bibliothèque standard.

Entrées : jeux ouverts de SNCF Réseau (et de SNCF Gares & Connexions pour le classement des gares) sur
https://ressources.data.sncf.com (licence ODbL), téléchargés en GeoJSON dans le dossier --brut (scripts/brut_rfn/ par
défaut, ignoré par git). Ils ne sont téléchargés que s'ils manquent, ou avec --telecharger.
Sorties : data/rfn_lignes.geojson, data/rfn_gares.geojson, data/rfn_meta.json (sources, dates, règles, bilan).

Lignes. La géométrie est celle du « Fichier de formes des lignes du RFN » (un segment = un statut). Chaque segment est
découpé en arêtes, et chaque arête reçoit ses attributs :
- électrifiée : ses deux extrémités sont des sommets d'une portion du jeu « Liste des lignes électrifiées » (même ligne) ;
  99,5 % des sommets de ce jeu sont des sommets des formes de lignes, d'où un rattachement exact, sans calcul de distance ;
- LGV / voie étroite : de même avec « Lignes LGV et par écartement » (catégorie `catlig`) ;
- nombre de voies : nombre de voies principales (VPL, VPA, hors évitements) du jeu « Fichier de formes des voies » qui
  passent à moins de TOLERANCE_VOIE_M de l'arête, puis lissage (les gares font monter le compte sur de courtes distances) ;
  à défaut de voie trouvée, repli sur le « Régime d'exploitation » (double voie = 2, sinon 1) ;
- usage : un tronçon (code_ligne, rg_troncon) exploité qui compte au moins une gare ouverte aux voyageurs est « mixte »,
  sinon « fret » (APPROXIMATION : aucun jeu ouvert ne donne l'usage des lignes).
Statuts : voir STATUTS. Les lignes déclassées, retranchées ou transférées en voie de service sont écartées.

Gares. Liste des gares du RFN (voyageurs O/N, fret O/N) dédoublonnée par code UIC ; le niveau d'intérêt vient du segment
DRG (A national, B régional, C local) du jeu « Gares de voyageurs », à défaut de celui de « Fréquentation en gares ».
Les gares ni voyageurs ni fret ne sont pas représentées.
"""
import argparse
import json
import math
import re
import sys
import unicodedata
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parent.parent
BRUT = Path(__file__).resolve().parent / 'brut_rfn'
SORTIE = RACINE / 'data'
HOTE = 'https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/'

# Jeux utilisés : identifiant du catalogue → rôle.
JEUX = {
    'formes-des-lignes-du-rfn': 'géométrie et statut des lignes',
    'liste-des-lignes-electrifiees': 'électrification',
    'lignes-lgv-et-par-ecartement': 'LGV et voie étroite',
    'fichier-de-formes-des-voies-du-reseau-ferre-national': 'nombre de voies, évitements',
    'regime-dexploitation-des-lignes': 'repli du nombre de voies',
    'liste-des-gares': 'gares du RFN (voyageurs, fret)',
    'gares-de-voyageurs': 'segment DRG des gares (national, régional, local)',
    'frequentation-gares': 'segment DRG de repli',
}

# Statut (colonne MNEMO) → groupe : E exploitée, N neutralisée (ligne suspendue), F fermée (ligne non exploitée).
# Écartés : déclassées (DEC V, DEC NV), retranchée, transférée en voie de service (VS), projet. Choix à valider : voir CLAUDE.md.
STATUTS = {'EXPLOITE': 'E', 'NEUT': 'N', 'NEUT DEF': 'N', 'S9A3': 'N',
           'FERME': 'F', 'FERME ND': 'F', 'FERME D': 'F', 'FERME MV': 'F', 'FERME DT': 'F'}
CATEGORIE_LGV = 'Ligne à grande vitesse'
CATEGORIE_ETROITE = 'Ligne du réseau conventionnel à voie étroite'
INTERET = {'A': 'N', 'B': 'R', 'C': 'L'}  # segment DRG → national, régional, local
ORDRE_SEGMENT = ('A', 'B', 'C')  # du plus important au moins important

# Relevé manuel sur la carte SNCF Réseau « Le réseau ferré en France » (mars 2026) : trois catégories de la légende qu'aucun
# jeu ouvert ne décrit (ni gestionnaire ni exploitant). Chaque entrée donne la catégorie cible, le code de ligne relevé
# (préfixe de `code_ligne`, ou None quand le relevé n'en donne pas) et les gares relevées.
# RÈGLE : un segment n'est reclassé que si le code de ligne ET les gares correspondent. Jamais par simple proximité.
#   - code de ligne : préfixe du `code_ligne` du segment (sans code relevé : codes portés par les gares relevées) ;
#   - gares : au moins `min_gares` gares relevées (nom, accents et « Saint/St » ignorés) à moins de GARE_MAX_M du tracé du segment ;
#   - le segment ne dépasse pas 1,6 × l'écart entre ses gares relevées les plus éloignées + 3 km (sinon il déborde du secteur relevé) ;
#     pour cet écart, une gare relevée à moins de EXTREMITE_MAX_M du tracé (bout de ligne) compte comme borne, sans compter dans les `min_gares`.
# Les entrées sans correspondance ne sont pas reclassées ; elles sont listées dans le bilan (`rfn_meta.json`).
# cible : 'lgv_autre' (LGV d'un autre gestionnaire, dessinée comme une LGV), 'suspendue_autre' (suspendue, reprise
# programmée par un autre gestionnaire), 'autre' (autre réseau ou exploitation touristique). Le statut du jeu ouvert est remplacé.
SOURCE_RELEVE = 'relevé manuel sur la carte SNCF Réseau « Le réseau ferré en France », mars 2026'
GARE_MAX_M = 1000.0
EXTREMITE_MAX_M = 2500.0
RELEVE_MANUEL = [
    {'nom': 'LGV Sud Europe Atlantique (Tours–Bordeaux)', 'cible': 'lgv_autre', 'code': '566',
     'gares': ['Noyant', 'Maillé', 'Clérac', 'Bussac', 'Montendre'], 'min_gares': 2, 'longue': True},
    {'nom': 'Montréjeau–Luchon', 'cible': 'suspendue_autre', 'code': None,
     'gares': ['Gourdan-Polignan', 'Avezac', 'Labarthe-Inard', 'Luchon'], 'min_gares': 2},
    {'nom': 'Vézelise–Mirecourt', 'cible': 'suspendue_autre', 'code': None,
     'gares': ['Xeuilley', 'Vézelise', 'Tantonville', 'Praye-sous-Vaudémont', 'Diarville', 'Hymont-Mattaincourt', 'Mirecourt'], 'min_gares': 2},
    {'nom': 'Cholet–Les Herbiers', 'cible': 'autre', 'code': '526', 'gares': ['Torfou', 'Brouzils'], 'min_gares': 2},
    {'nom': 'Secteur de Saint-Lô', 'cible': 'autre', 'code': '414', 'gares': ['Condé-sur-Vire', 'Pont-Hébert', 'Marigny'], 'min_gares': 2},
    {'nom': 'Le Havre', 'cible': 'autre', 'code': '341', 'gares': ['Harfleur', 'Saint-Laurent', 'Étainhus'], 'min_gares': 2},
    {'nom': 'Rivesaltes–Estagel–Saint-Paul-de-Fenouillet', 'cible': 'autre', 'code': '676',
     'gares': ['Rivesaltes', 'Estagel', 'Saint-Paul-de-Fenouillet'], 'min_gares': 2},
    {'nom': 'Béziers (Colombiers, Cazouls, Nissan)', 'cible': 'autre', 'code': '640', 'gares': ['Colombiers', 'Cazouls', 'Nissan'], 'min_gares': 2},
    {'nom': 'Saint-Quentin–Montescourt–Essigny-le-Petit', 'cible': 'autre', 'code': '242',
     'gares': ['Saint-Quentin', 'Montescourt', 'Essigny-le-Petit'], 'min_gares': 2},
    {'nom': 'Secteur d\'Ambert', 'cible': 'autre', 'code': '785', 'gares': ['Ambert'], 'min_gares': 1},
    {'nom': 'Veauche–Bonson–Bouthéon', 'cible': 'autre', 'code': '578', 'gares': ['Veauche', 'Bonson', 'Bouthéon'], 'min_gares': 2},
    {'nom': 'Veauche–Bonson–Bouthéon (lu aussi 782)', 'cible': 'autre', 'code': '782', 'gares': ['Veauche', 'Bonson', 'Bouthéon'], 'min_gares': 2},
    {'nom': 'Rethel–Amagne-Lucquy–Attigny', 'cible': 'autre', 'code': '210', 'gares': ['Rethel', 'Amagne', 'Attigny'], 'min_gares': 2},
    {'nom': 'Secteur de Bordeaux (position inconnue)', 'cible': 'autre', 'code': '583', 'gares': ['Bordeaux'], 'min_gares': 2},
    {'nom': 'Port de Dunkerque', 'cible': 'autre', 'code': None, 'gares': ['Maritime-Mardyck', 'Port-Ouest', 'Port-Est'], 'min_gares': 2},
    {'nom': 'Calais–Fréthun', 'cible': 'autre', 'code': None, 'gares': ['Calais', 'Fréthun'], 'min_gares': 2},
    {'nom': 'Royan–Saujon–Gémozac', 'cible': 'autre', 'code': None, 'gares': ['Royan', 'Saujon', 'Gémozac'], 'min_gares': 2},
    {'nom': 'Bort-les-Orgues–Lugarde-Marchastel', 'cible': 'autre', 'code': None, 'gares': ['Bort-les-Orgues', 'Lugarde'], 'min_gares': 2},
    {'nom': 'Leyment–Lagnieu', 'cible': 'autre', 'code': None, 'gares': ['Leyment', 'Lagnieu'], 'min_gares': 2},
    {'nom': 'Brassac-les-Mines–Sainte-Florine–Paulhaguet', 'cible': 'autre', 'code': None,
     'gares': ['Brassac-les-Mines', 'Sainte-Florine', 'Paulhaguet'], 'min_gares': 2},
    {'nom': 'Médoc (Margaux, Listrac)', 'cible': 'autre', 'code': None, 'gares': ['Margaux', 'Listrac'], 'min_gares': 2},
]
# LGV absente du fichier de formes (jeu « Lignes LGV et par écartement » seulement) : Perpignan → frontière, d'un autre gestionnaire.
# Le code 837000 est celui du jeu ; les gares (Le Soler à 1,7 km, Le Boulou-Perthus à 2,4 km) sont sur la ligne classique voisine, d'où la
# tolérance EXTREMITE_MAX_M au lieu de GARE_MAX_M : correspondance plus lâche que les autres, signalée dans le rapport.
LGV_AUTRE_AJOUTEE = {'nom': 'LGV Perpignan–frontière', 'code': '837000', 'gares': ['Le Soler', 'Boulou', 'Perthus'], 'min_gares': 2}

KX, KY = 76630.0, 111190.0  # mètres par degré de longitude et de latitude (équirectangulaire autour de 46,5° N)
TOLERANCE_VOIE_M = 15.0  # distance maximale d'une voie à l'arête pour être comptée
LONGUEUR_MIN_VOIES_M = 1000.0  # un nombre de voies qui ne dure pas 1 km est absorbé par son voisin (gares, évitements)
SIMPLIFICATION_M = 12.0  # tolérance de Douglas-Peucker
DECIMALES = 5  # 1 m
DISTANCE_MEME_GARE_M = 2000.0  # projections d'un même code UIC fusionnées en deçà


def telecharger(brut, forcer):
    """Télécharge chaque jeu en GeoJSON (si absent), et ses métadonnées (dates, licence) dans meta_sources.json."""
    brut.mkdir(parents=True, exist_ok=True)
    meta = {}
    for ds in JEUX:
        chemin = brut / f'{ds}.geojson'
        if forcer or not chemin.exists():
            print(f'téléchargement de {ds}…', file=sys.stderr)
            lire(HOTE + f'{ds}/exports/geojson?limit=-1', chemin)
        fiche = brut / f'{ds}.meta.json'
        if forcer or not fiche.exists():
            lire(HOTE + ds, fiche)
        m = json.loads(fiche.read_text())['metas']['default']
        meta[ds] = {'titre': m.get('title'), 'editeur': m.get('publisher'), 'licence': m.get('license'),
                    'modifie': (m.get('modified') or '')[:10], 'donnees_du': (m.get('data_processed') or '')[:10]}
    return meta


def lire(url, chemin):
    for essai in range(4):
        try:
            with urllib.request.urlopen(url, timeout=600) as rep, open(chemin, 'wb') as f:
                while bloc := rep.read(1 << 20):
                    f.write(bloc)
            return
        except Exception as e:
            if essai == 3:
                raise
            print(f'  nouvel essai ({e})', file=sys.stderr)
            time.sleep(2 ** (essai + 1))


def charger(brut, ds):
    return json.loads((brut / f'{ds}.geojson').read_text())['features']


def sommets(geometrie):
    return geometrie['coordinates'] if geometrie['type'] == 'LineString' else [c for ligne in geometrie['coordinates'] for c in ligne]


def cle(c):
    return (round(c[0], 6), round(c[1], 6))


def metres(c):
    return (c[0] * KX, c[1] * KY)


def sommets_par_ligne(features, champ, filtre=None):
    """code_ligne → {sommet → valeurs du champ des portions qui le contiennent}."""
    d = defaultdict(lambda: defaultdict(set))
    for f in features:
        p = f['properties']
        if f['geometry'] is None or (filtre and not filtre(p)):
            continue
        for c in sommets(f['geometry']):
            d[p['code_ligne']][cle(c)].add(p[champ])
    return d


def distances_aux_segments(points, a, b):
    """Distance de chaque point à chaque segment [a, b] (tableaux numpy en mètres) : forme (points, segments)."""
    ab = b - a
    carre = (ab ** 2).sum(1)
    carre[carre == 0] = 1e-9
    t = np.clip(((points[:, None, :] - a[None]) * ab[None]).sum(2) / carre[None], 0, 1)
    projete = a[None] + t[..., None] * ab[None]
    return np.sqrt(((points[:, None, :] - projete) ** 2).sum(2))


def compter_voies(segment, voies):
    """Nombre de voies principales voisines de chaque arête d'un segment exploité (tableau d'entiers, 0 = aucune trouvée)."""
    c = np.array([metres(p) for p in segment]) if len(segment) else np.zeros((0, 2))
    milieux = (c[:-1] + c[1:]) / 2
    bas, haut = milieux.min(0) - TOLERANCE_VOIE_M, milieux.max(0) + TOLERANCE_VOIE_M
    par_nom = defaultdict(lambda: np.zeros(len(milieux), bool))
    for nom, vc in voies:
        if vc[:, 0].max() < bas[0] or vc[:, 0].min() > haut[0] or vc[:, 1].max() < bas[1] or vc[:, 1].min() > haut[1]:
            continue
        lo, hi = vc.min(0) - TOLERANCE_VOIE_M, vc.max(0) + TOLERANCE_VOIE_M
        sel = np.where((milieux[:, 0] >= lo[0]) & (milieux[:, 0] <= hi[0]) & (milieux[:, 1] >= lo[1]) & (milieux[:, 1] <= hi[1]))[0]
        if len(sel) == 0:
            continue
        proche = distances_aux_segments(milieux[sel], vc[:-1], vc[1:]).min(1) <= TOLERANCE_VOIE_M
        par_nom[nom][sel[proche]] = True
    total = np.zeros(len(milieux), int)
    for presente in par_nom.values():
        total += presente
    return total


def lisser(valeurs, longueurs, minimum):
    """Valeur lissée de chaque arête : toute plage de valeurs plus courte que `minimum` (en mètres) est absorbée par le plus
    long de ses voisins, en commençant par la plus courte."""
    plages = []  # [valeur, longueur, nombre d'arêtes]
    for v, l in zip(valeurs, longueurs):
        if plages and plages[-1][0] == v:
            plages[-1][1] += l
            plages[-1][2] += 1
        else:
            plages.append([v, l, 1])
    while len(plages) > 1:
        i = min(range(len(plages)), key=lambda k: plages[k][1])
        if plages[i][1] >= minimum:
            break
        k = max((j for j in (i - 1, i + 1) if 0 <= j < len(plages)), key=lambda j: plages[j][1])
        plages[k][1] += plages[i][1]
        plages[k][2] += plages[i][2]
        del plages[i]
        fusion = [plages[0]]
        for plage in plages[1:]:
            if fusion[-1][0] == plage[0]:
                fusion[-1][1] += plage[1]
                fusion[-1][2] += plage[2]
            else:
                fusion.append(plage)
        plages = fusion
    return [v for v, _, n in plages for _ in range(n)]


def douglas_peucker(points, tolerance):
    """Simplification de Douglas-Peucker (points en mètres), itérative ; garde toujours les extrémités."""
    n = len(points)
    if n < 3:
        return list(range(n))
    garde = [False] * n
    garde[0] = garde[-1] = True
    pile = [(0, n - 1)]
    while pile:
        d, f = pile.pop()
        if f <= d + 1:
            continue
        ax, ay = points[d]
        bx, by = points[f]
        dx, dy = bx - ax, by - ay
        norme = math.hypot(dx, dy)
        pire, rang = -1.0, d
        for i in range(d + 1, f):
            px, py = points[i]
            e = math.hypot(px - ax, py - ay) if norme == 0 else abs(dx * (ay - py) - dy * (ax - px)) / norme
            if e > pire:
                pire, rang = e, i
        if pire > tolerance:
            garde[rang] = True
            pile.append((d, rang))
            pile.append((rang, f))
    return [i for i in range(n) if garde[i]]


def geometrie_simplifiee(coordonnees):
    pts = [metres(c) for c in coordonnees]
    return [[round(coordonnees[i][0], DECIMALES), round(coordonnees[i][1], DECIMALES)] for i in douglas_peucker(pts, SIMPLIFICATION_M)]


def construire_gares(brut, bilan):
    rfn = charger(brut, 'liste-des-gares')
    gc = charger(brut, 'gares-de-voyageurs')
    freq = charger(brut, 'frequentation-gares')

    def meilleur(segments):
        return min(segments, key=ORDRE_SEGMENT.index)

    segment_gc, nom_gc = {}, {}
    for f in gc:
        p = f['properties']
        codes = [c.strip() for c in (p['codes_uic'] or '').split(';') if c.strip()]
        segs = [s.strip() for s in (p['segment_drg'] or '').split(';') if s.strip() in ORDRE_SEGMENT]
        if not codes or not segs:
            continue
        for i, code in enumerate(codes):
            # une liste de segments de même longueur que celle des codes est lue code par code, sinon on garde le plus important
            segment_gc[code] = segs[i] if len(segs) == len(codes) else meilleur(segs)
            nom_gc[code] = p['nom']
    segment_freq = {f['properties']['code_uic_complet']: f['properties']['segmentation_drg']
                    for f in freq if f['properties']['segmentation_drg'] in ORDRE_SEGMENT}

    par_code = defaultdict(list)
    for f in rfn:
        par_code[f['properties']['code_uic']].append(f)
    gares = []
    for code, fiches in par_code.items():
        # projections d'un même code UIC : fusionnées si elles sont proches, sinon séparées
        groupes = []
        for f in fiches:
            x, y = metres(f['geometry']['coordinates'])
            for g in groupes:
                if math.hypot(x - g['x'], y - g['y']) <= DISTANCE_MEME_GARE_M:
                    g['fiches'].append(f)
                    break
            else:
                groupes.append({'x': x, 'y': y, 'fiches': [f]})
        if len(groupes) > 1:
            bilan['gares : codes UIC projetés en plusieurs endroits éloignés (> 2 km), gardés séparément'] += 1
        for g in groupes:
            p0 = g['fiches'][0]['properties']
            voyageurs = any(f['properties']['voyageurs'] == 'O' for f in g['fiches'])
            fret = any(f['properties']['fret'] == 'O' for f in g['fiches'])
            if not voyageurs and not fret:
                bilan['gares ignorées : ni voyageurs ni fret'] += 1
                continue
            interet, source = '', ''
            if voyageurs:
                if code in segment_gc:
                    interet, source = INTERET[segment_gc[code]], 'drg'
                elif code in segment_freq:
                    interet, source = INTERET[segment_freq[code]], 'frequentation'
                else:
                    interet, source = INTERET['C'], 'defaut'
            nom = nom_gc.get(code) or p0['libelle']
            c = g['fiches'][0]['geometry']['coordinates']
            gares.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(c[0], DECIMALES), round(c[1], DECIMALES)]},
                          'properties': {'n': nom, 'u': code, 'i': interet, 'd': int(voyageurs), 'f': int(fret),
                                         'c': (p0['commune'] or '').title(), 's': source}})
    gares.sort(key=lambda f: (f['properties']['u'], f['geometry']['coordinates']))
    bilan['gares écrites'] = len(gares)
    for f in gares:
        p = f['properties']
        bilan['gares : ' + ('desservie voyageurs, ' if p['d'] else 'non desservie voyageurs (fret), ')
              + {'N': 'intérêt national', 'R': 'intérêt régional', 'L': 'intérêt local', '': 'sans niveau'}[p['i']]] += 1
        if p['d']:
            bilan['gares : niveau d\'intérêt issu de ' + {'drg': 'Gares de voyageurs (segment DRG)', 'frequentation': 'Fréquentation en gares',
                                                          'defaut': 'aucun jeu (local par défaut)'}[p['s']]] += 1
    return gares


def nom_normalise(texte):
    """Nom de gare sans accents ni ponctuation, « Saint/Sainte » abrégés comme dans le jeu des gares."""
    t = unicodedata.normalize('NFD', texte or '').encode('ascii', 'ignore').decode().lower()
    t = re.sub(r'[^a-z0-9]+', ' ', t).strip()
    return re.sub(r'\bsainte\b', 'ste', re.sub(r'\bsaint\b', 'st', t))


def distance_polyligne_m(point, coords):
    px, py = metres(point)
    meilleure = float('inf')
    for a, b in zip(coords, coords[1:]):
        ax, ay = metres(a)
        dx, dy = metres(b)[0] - ax, metres(b)[1] - ay
        carre = dx * dx + dy * dy
        t = 0.0 if carre == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / carre))
        meilleure = min(meilleure, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return meilleure


def km_polyligne(coords):
    return sum(math.hypot(*(a - b for a, b in zip(metres(c1), metres(c0)))) for c0, c1 in zip(coords, coords[1:])) / 1000


def gares_nommees(gares, nom_norm):
    """Gares dont le libellé normalisé est ce nom ou le contient comme suite de mots entiers."""
    return [(c, pos) for libelle, c, pos in gares if (' ' + nom_norm + ' ') in (' ' + libelle + ' ')]


def rapprocher_releve(formes, gares_brutes):
    """Applique RELEVE_MANUEL : renvoie ({indice du segment dans `formes` → cible}, rapport par entrée)."""
    gares = [(nom_normalise(g['properties']['libelle']), g['properties']['code_ligne'], g['geometry']['coordinates'])
             for g in gares_brutes if g['geometry']]
    reclasses, rapport = {}, []
    for entree in RELEVE_MANUEL:
        noms = [(n, nom_normalise(n)) for n in entree['gares']]
        trouvees = {n: gares_nommees(gares, nn) for n, nn in noms}  # nom relevé → [(code_ligne de la gare, position)]
        if entree['code']:
            codes = None
        else:  # sans code relevé : les codes portés par les gares relevées
            codes = {c for v in trouvees.values() for c, _ in v}
        retenus, candidats = [], []
        for i, f in enumerate(formes):
            p, coords = f['properties'], f['geometry']['coordinates']
            if p['mnemo'] == 'VS' or len(coords) < 2 or i in reclasses:
                continue
            if entree['code'] is not None:
                if not p['code_ligne'].startswith(entree['code']):
                    continue
            elif p['code_ligne'] not in codes:
                continue
            proches = {n: [pos for _, pos in v if distance_polyligne_m(pos, coords) <= GARE_MAX_M] for n, v in trouvees.items()}
            proches = {n: v for n, v in proches.items() if v}
            lg = km_polyligne(coords)
            bornes = [pos for v in trouvees.values() for _, pos in v if distance_polyligne_m(pos, coords) <= EXTREMITE_MAX_M] if proches else []
            ecart = max([math.hypot(*(a - b for a, b in zip(metres(x), metres(y)))) / 1000 for x in bornes for y in bornes] or [0])
            candidats.append((p['code_ligne'], p['mnemo'], round(lg, 1), sorted(proches)))
            if len(proches) < entree['min_gares']:
                continue
            if len(proches) >= 2 and lg > 1.6 * ecart + 3 and not entree.get('longue'):
                continue
            retenus.append(i)
            reclasses[i] = entree['cible']
        rapport.append({'entree': entree['nom'], 'cible': entree['cible'], 'code_releve': entree['code'],
                        'reclasses': [{'code_ligne': formes[i]['properties']['code_ligne'], 'statut_jeu_ouvert': formes[i]['properties']['mnemo'],
                                       'km': round(km_polyligne(formes[i]['geometry']['coordinates']), 1),
                                       'gares': sorted(n for n, v in trouvees.items() if any(
                                           distance_polyligne_m(pos, formes[i]['geometry']['coordinates']) <= GARE_MAX_M for _, pos in v))}
                                      for i in retenus],
                        'non_retenus': [c for c in candidats if c[3] and not any(
                            c[0] == formes[i]['properties']['code_ligne'] and c[2] == round(km_polyligne(formes[i]['geometry']['coordinates']), 1) for i in retenus)]})
    return reclasses, rapport


def construire_lignes(brut, bilan, bilan_releve):
    formes = charger(brut, 'formes-des-lignes-du-rfn')
    electrifie = sommets_par_ligne(charger(brut, 'liste-des-lignes-electrifiees'), 'elect')
    categorie = sommets_par_ligne(charger(brut, 'lignes-lgv-et-par-ecartement'), 'catlig')
    regime = sommets_par_ligne(charger(brut, 'regime-dexploitation-des-lignes'), 'exploitati')
    voies_brutes = charger(brut, 'fichier-de-formes-des-voies-du-reseau-ferre-national')

    voies = defaultdict(list)  # code_ligne → [(nom de voie, tableau de points en mètres)]
    evitements = []
    for f in voies_brutes:
        p = f['properties']
        if p['type_voie'] == 'VS':
            continue
        if p['nom_voie'] == 'EVIT':
            evitements.append(f)
        else:
            voies[p['code_ligne']].append((p['nom_voie'], np.array([metres(c) for c in sommets(f['geometry'])])))

    # Tronçons (code_ligne, rg_troncon) comptant au moins une gare ouverte aux voyageurs.
    avec_voyageurs = {(g['properties']['code_ligne'], g['properties']['rg_troncon'])
                      for g in charger(brut, 'liste-des-gares') if g['properties']['voyageurs'] == 'O'}

    reclasses, rapport = rapprocher_releve(formes, charger(brut, 'liste-des-gares'))
    bilan_releve.extend(rapport)

    traits = []
    for indice, f in enumerate(formes):
        p = f['properties']
        cible = reclasses.get(indice)
        statut = {'suspendue_autre': 'R', 'autre': 'A'}.get(cible) or STATUTS.get(p['mnemo'])
        if cible:
            bilan['km reclassés par le relevé manuel, ' + cible] += km_polyligne(f['geometry']['coordinates'])
        if statut is None:
            bilan['segments écartés (statut ' + p['mnemo'] + ')'] += 1
            continue
        coords = f['geometry']['coordinates']
        if len(coords) < 2:
            continue
        code, rang = p['code_ligne'], p['rg_troncon']
        m = [metres(c) for c in coords]
        longueurs = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(m, m[1:])]
        if statut != 'E':
            # Lignes non exploitées, suspendues, ou reclassées par le relevé (R, A) : un seul style, sans voies ni électrification.
            attributs = [(statut, '', 0, 0)] * len(longueurs)
        else:
            usage = 'mixte' if (code, rang) in avec_voyageurs else 'fret'
            nb = compter_voies(coords, voies.get(code, []))
            attributs = []
            brut_voies = []
            for i, (a, b) in enumerate(zip(coords, coords[1:])):
                ka, kb = cle(a), cle(b)
                ev, cv, rg = electrifie.get(code, {}), categorie.get(code, {}), regime.get(code, {})
                cats = (cv.get(ka, set()) & cv.get(kb, set())) or cv.get(ka, set()) or cv.get(kb, set())
                if cible == 'lgv_autre':
                    cat = 'lgv_autre'
                elif CATEGORIE_LGV in cats:
                    cat = 'lgv'
                elif CATEGORIE_ETROITE in cats:
                    cat = 'metrique'
                else:
                    cat = usage
                n = min(int(nb[i]), 3)
                if n == 0:
                    r = (rg.get(ka, set()) & rg.get(kb, set())) or rg.get(ka, set()) or rg.get(kb, set())
                    n = 2 if r == {'Double voie'} else 1
                    bilan['arêtes exploitées sans voie trouvée (repli sur le régime d\'exploitation ou 1 voie), km'] += longueurs[i] / 1000
                brut_voies.append(n)
                attributs.append((statut, cat, 0, int(ka in ev and kb in ev)))
            # Lissage du nombre de voies, puis assemblage des attributs.
            lisses = lisser(brut_voies, longueurs, LONGUEUR_MIN_VOIES_M)
            attributs = [(s, c, lisses[i], e) for i, (s, c, _, e) in enumerate(attributs)]
        # Plages d'arêtes consécutives de mêmes attributs → un trait.
        debut = 0
        for i in range(1, len(attributs) + 1):
            if i == len(attributs) or attributs[i] != attributs[debut]:
                s, c, v, e = attributs[debut]
                morceau = coords[debut:i + 1]
                longueur_km = sum(longueurs[debut:i]) / 1000
                bilan['longueur km, statut ' + s] += longueur_km
                if s == 'E':
                    bilan['longueur km, exploitée, catégorie ' + c] += longueur_km
                    bilan['longueur km, exploitée, ' + ('électrifiée' if e else 'non électrifiée')] += longueur_km
                    bilan['longueur km, exploitée, voies ' + str(v)] += longueur_km
                props = {'g': s, 'l': code}
                if s == 'E':
                    props.update({'c': c, 'v': v, 'e': e})
                traits.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': geometrie_simplifiee(morceau)},
                               'properties': props})
                debut = i
    # LGV d'un autre gestionnaire absente du fichier de formes : tracé du jeu « Lignes LGV et par écartement », si les gares relevées
    # sont bien le long du tracé (même règle que RELEVE_MANUEL).
    ajout = LGV_AUTRE_AJOUTEE
    gares_brutes = charger(brut, 'liste-des-gares')
    morceaux = [f for f in charger(brut, 'lignes-lgv-et-par-ecartement') if f['properties']['code_ligne'] == ajout['code'] and f['geometry']]
    # Le jeu répète le tracé (un enregistrement sans PK en double) : un seul exemplaire de chaque tracé.
    morceaux = list({json.dumps(m['geometry']['coordinates']): m for m in morceaux}.values())
    noms = {n: nom_normalise(n) for n in ajout['gares']}
    gares_norm = [(nom_normalise(g['properties']['libelle']), g['properties']['code_ligne'], g['geometry']['coordinates'])
                  for g in gares_brutes if g['geometry']]
    proches = {n for n, nn in noms.items() for _, pos in gares_nommees(gares_norm, nn)
               if any(distance_polyligne_m(pos, m['geometry']['coordinates']) <= EXTREMITE_MAX_M for m in morceaux)}
    km_ajoutes = 0.0
    if len(proches) >= ajout['min_gares']:
        ev = electrifie.get(ajout['code'], {})
        for m in morceaux:
            coords = m['geometry']['coordinates']
            km_ajoutes += km_polyligne(coords)
            elec = int(all(cle(c) in ev for c in coords))
            traits.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': geometrie_simplifiee(coords)},
                           'properties': {'g': 'E', 'c': 'lgv_autre', 'v': 2, 'e': elec, 'l': ajout['code']}})
        bilan['km reclassés par le relevé manuel, lgv_autre'] += km_ajoutes
    bilan_releve.append({'entree': ajout['nom'], 'cible': 'lgv_autre', 'code_releve': ajout['code'],
                         'reclasses': [{'code_ligne': ajout['code'], 'statut_jeu_ouvert': 'absent du fichier de formes (jeu LGV)',
                                        'km': round(km_ajoutes, 1), 'gares': sorted(proches)}] if km_ajoutes else [], 'non_retenus': []})
    # Évitements : voies nommées EVIT du jeu des voies (lignes exploitées uniquement).
    for f in evitements:
        for ligne in (f['geometry']['coordinates'] if f['geometry']['type'] == 'MultiLineString' else [f['geometry']['coordinates']]):
            if len(ligne) >= 2:
                traits.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': geometrie_simplifiee(ligne)},
                               'properties': {'g': 'E', 'c': 'evit', 'v': 1, 'e': 0, 'l': f['properties']['code_ligne']}})
                bilan['évitements (EVIT)'] += 1
    bilan['traits de lignes écrits'] = len(traits)
    return traits


def ecrire_geojson(chemin, features):
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False, separators=(',', ':')))
        f.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--brut', type=Path, default=BRUT, help='dossier des données brutes téléchargées')
    parser.add_argument('--telecharger', action='store_true', help='télécharge à nouveau les jeux')
    args = parser.parse_args()
    meta = telecharger(args.brut, args.telecharger)
    bilan = Counter()
    gares = construire_gares(args.brut, bilan)
    rapport_releve = []
    traits = construire_lignes(args.brut, bilan, rapport_releve)
    ecrire_geojson(SORTIE / 'rfn_lignes.geojson', traits)
    ecrire_geojson(SORTIE / 'rfn_gares.geojson', gares)
    sortie = {
        'genere_le': date.today().isoformat(),
        'sources': meta,
        'parametres': {'tolerance_voie_m': TOLERANCE_VOIE_M, 'longueur_min_voies_m': LONGUEUR_MIN_VOIES_M,
                       'simplification_m': SIMPLIFICATION_M, 'decimales': DECIMALES},
        'statuts': STATUTS,
        'releve_manuel': {'source': SOURCE_RELEVE, 'gare_max_m': GARE_MAX_M, 'entrees': rapport_releve},
        'bilan': {k: round(v, 1) if isinstance(v, float) else v for k, v in sorted(bilan.items())},
    }
    (SORTIE / 'rfn_meta.json').write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for k, v in sorted(bilan.items()):
        print(f'{k} : {round(v) if isinstance(v, float) else v}', file=sys.stderr)


if __name__ == '__main__':
    main()
