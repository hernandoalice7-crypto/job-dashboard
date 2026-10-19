"""Chef d'orchestre : sources -> filtres -> score -> mémoire -> page web."""

import importlib
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from jobfinder import matching, report, storage

RACINE = Path(__file__).resolve().parent.parent
FICHIER_NOUVELLES = Path(os.environ.get("NOUVELLES_FICHIER", RACINE / "nouvelles_offres.md"))


def lire_config():
    with open(RACINE / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def lancer_sources(cfg):
    """Lance chaque source activée. Une source qui plante ne bloque jamais les autres.
    Renvoie (toutes_les_offres, erreurs_par_source)."""
    offres, erreurs = [], {}
    for nom, active in (cfg.get("sources") or {}).items():
        if not active:
            continue
        try:
            module = importlib.import_module(f"jobfinder.sources.{nom}")
        except ModuleNotFoundError:
            erreurs[nom] = "source pas encore installée"
            print(f"[{nom}] pas encore installée, ignorée")
            continue
        try:
            trouvees = module.fetch(cfg) or []
            print(f"[{nom}] {len(trouvees)} offres lues")
            offres.extend(trouvees)
        except Exception as e:
            erreurs[nom] = f"{type(e).__name__}: {str(e)[:120]}"
            print(f"[{nom}] ERREUR : {erreurs[nom]}")
            traceback.print_exc()
    return offres, erreurs


def dedoublonner(offres):
    """Supprime les doublons (même lien)."""
    vues, uniques = set(), []
    for o in offres:
        if o.id not in vues:
            vues.add(o.id)
            uniques.append(o)
    return uniques


def ecrire_message_nouvelles(nouvelles, maj):
    """Prépare le texte de l'e-mail (une « issue » GitHub). Fichier vide s'il n'y a rien."""
    if not nouvelles:
        if FICHIER_NOUVELLES.exists():
            FICHIER_NOUVELLES.unlink()
        return
    lignes = [f"{len(nouvelles)} nouvelle(s) offre(s) au {maj} :", ""]
    for o in sorted(nouvelles, key=lambda x: -x.score)[:30]:
        lieu = f" – {o.location}" if o.location else ""
        lignes.append(f"- **{o.score}/100** · [{o.title}]({o.url}) · {o.company}{lieu}")
    lignes += ["", "Ouvre ton dashboard pour tout voir et filtrer."]
    FICHIER_NOUVELLES.write_text("\n".join(lignes), encoding="utf-8")


def main():
    cfg = lire_config()
    maintenant = datetime.now(ZoneInfo("Europe/Paris"))
    maj = maintenant.strftime("%d/%m/%Y à %H:%M")

    offres, erreurs = lancer_sources(cfg)
    offres = dedoublonner(offres)
    gardees, stats = matching.traiter(offres, cfg)

    # Toutes les sources activées apparaissent dans l'onglet « Sources », même à 0 offre
    for nom, active in (cfg.get("sources") or {}).items():
        if active:
            stats.setdefault(nom, {"trouvees": 0, "gardees": 0, "retirees": {}})
    for nom, message in erreurs.items():
        stats.setdefault(nom, {"trouvees": 0, "gardees": 0, "retirees": {}})["erreur"] = message

    # Mémoire des offres déjà vues -> badge NOUVEAU
    memoire = storage.charger()
    nouvelles = storage.marquer_nouvelles(gardees, memoire, maintenant.date())
    storage.nettoyer(memoire, maintenant.date())
    storage.sauvegarder(memoire)

    gardees.sort(key=lambda o: (-o.score, o.company.lower()))
    report.generer(gardees, stats, maj, nouvelles)

    if cfg.get("notifications", {}).get("email_si_nouvelles_offres", True):
        ecrire_message_nouvelles([o for o in gardees if o.is_new], maj)

    print(f"Terminé : {len(offres)} offres lues, {len(gardees)} gardées, {nouvelles} nouvelles.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
