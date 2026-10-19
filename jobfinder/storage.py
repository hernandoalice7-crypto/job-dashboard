"""Mémoire des offres déjà vues (seen_offers.json) pour le badge NOUVEAU."""

import json
from datetime import timedelta
from pathlib import Path

# Le fichier est à la racine du dépôt (à côté de config.yaml)
FICHIER = Path(__file__).resolve().parent.parent / "seen_offers.json"

# Une offre qu'on n'a pas revue depuis ce nombre de jours est oubliée
OUBLI_APRES_JOURS = 90


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


def marquer_nouvelles(offres, memoire, aujourdhui):
    """Met le badge NOUVEAU sur les offres jamais vues, puis les mémorise.
    Renvoie le nombre de nouvelles offres.

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
            }
            if not premier_lancement:
                o.is_new = True
                o.badges.insert(0, "NOUVEAU")
                nouvelles += 1
        else:
            connue["derniere_vue"] = jour
    return nouvelles


def nettoyer(memoire, aujourdhui):
    """Oublie les offres qu'on n'a pas revues depuis longtemps (offres expirées)."""
    limite = (aujourdhui - timedelta(days=OUBLI_APRES_JOURS)).isoformat()
    memoire["offres"] = {
        k: v for k, v in memoire["offres"].items()
        if v.get("derniere_vue", "") >= limite
    }


def sauvegarder(memoire):
    """Écrit la mémoire dans seen_offers.json."""
    with open(FICHIER, "w", encoding="utf-8") as f:
        json.dump(memoire, f, ensure_ascii=False, indent=1, sort_keys=True)
