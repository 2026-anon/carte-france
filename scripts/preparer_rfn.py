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
import sys
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


def construire_lignes(brut, bilan):
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

    traits = []
    for f in formes:
        p = f['properties']
        statut = STATUTS.get(p['mnemo'])
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
            # Lignes non exploitées ou suspendues : un seul style, sans voies ni électrification.
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
                if CATEGORIE_LGV in cats:
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
    traits = construire_lignes(args.brut, bilan)
    ecrire_geojson(SORTIE / 'rfn_lignes.geojson', traits)
    ecrire_geojson(SORTIE / 'rfn_gares.geojson', gares)
    sortie = {
        'genere_le': date.today().isoformat(),
        'sources': meta,
        'parametres': {'tolerance_voie_m': TOLERANCE_VOIE_M, 'longueur_min_voies_m': LONGUEUR_MIN_VOIES_M,
                       'simplification_m': SIMPLIFICATION_M, 'decimales': DECIMALES},
        'statuts': STATUTS,
        'bilan': {k: round(v, 1) if isinstance(v, float) else v for k, v in sorted(bilan.items())},
    }
    (SORTIE / 'rfn_meta.json').write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for k, v in sorted(bilan.items()):
        print(f'{k} : {round(v) if isinstance(v, float) else v}', file=sys.stderr)


if __name__ == '__main__':
    main()
