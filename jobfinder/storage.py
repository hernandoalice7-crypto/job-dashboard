"""Mémoire des offres (seen_offers.json) : badge NOUVEAU + archive des offres."""

import json
from datetime import timedelta
from pathlib import Path

from jobfinder.models import Offer

# Le fichier est à la racine du dépôt (à côté de config.yaml)
FICHIER = Path(__file__).resolve().parent.parent / "seen_offers.json"

OUBLI_APRES_JOURS = 36500   # 100 ans : on n'oublie jamais une offre
GARDER_JOURS = 36500        # une offre non revue reste affichée sans limite

CHAMPS = ("title", "company", "url", "source", "location", "published",
          "start_date", "contract", "duration_months", "salary", "description")


def _champs(o):
    """Les informations de l'offre à conserver."""
    d = {k: getattr(o, k) for k in CHAMPS}
    d["description"] = (d["description"] or "")[:1500]
    return d


def charger():
    """Lit la mémoire. Si le fichier n'existe pas ou est abîmé, repart de zéro."""
    try:
        with open(FICHIER, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("offres"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"offres": {}}


def offres_archivees(memoire, ids_du_jour, aujourdhui):
    """Offres vues récemment mais absentes des sources aujourd'hui."""
    limite = (aujourdhui - timedelta(days=GARDER_JOURS)).isoformat()
    resultat = []
    for ident, v in memoire["offres"].items():
        if ident in ids_du_jour:
            continue
        data = v.get("offre")
        if not data or v.get("derniere_vue", "") < limite:
            continue
        try:
            resultat.append(Offer(**data))
        except TypeError:
            continue
    return resultat


def marquer_nouvelles(offres, memoire, aujourdhui):
    """Met le badge NOUVEAU sur les offres jamais vues, puis les mémorise
    (avec leurs informations). Renvoie le nombre de nouvelles offres.

    Au tout premier lancement, la mémoire est vide : on mémorise tout sans mettre
    de badge, sinon toutes les offres seraient « nouvelles »."""
    jour = aujourdhui.isoformat()
    premier_lancement = not memoire["offres"]
    nouvelles = 0

    for o in offres:
        connue = memoire["offres"].get(o.id)
        if connue is None:
            memoire["offres"][o.id] = {
                "titre": o.title,
                "entreprise": o.company,
                "vue_le": jour,
                "derniere_vue": jour,
                "offre": _champs(o),
            }
            if not premier_lancement:
                o.is_new = True
                o.badges.insert(0, "NOUVEAU")
                nouvelles += 1
        else:
            connue["derniere_vue"] = jour
            connue["offre"] = _champs(o)
    return nouvelles


def nettoyer(memoire, aujourdhui):
    """Oublie les offres qu'on n'a pas revues depuis très longtemps."""
    limite = (aujourdhui - timedelta(days=OUBLI_APRES_JOURS)).isoformat()
    memoire["offres"] = {
        k: v for k, v in memoire["offres"].items()
        if v.get("derniere_vue", "") >= limite
    }


def sauvegarder(memoire):
    """Écrit la mémoire dans seen_offers.json."""
    with open(FICHIER, "w", encoding="utf-8") as f:
        json.dump(memoire, f, ensure_ascii=False, indent=1, sort_keys=True)
