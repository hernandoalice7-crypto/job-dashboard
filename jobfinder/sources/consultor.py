"""Source : offres de stage sur Consultor (consultor.fr)."""

import re
import time

import requests
from bs4 import BeautifulSoup

from jobfinder.models import Offer

BASE = "https://www.consultor.fr"
URL = BASE + "/carrieres/offre-d-emploi"
PAS = 15              # nombre d'offres par page chez Consultor
MAX_PAGES = 8         # sécurité : on ne lit jamais plus de 8 pages
ENTETES = {"User-Agent": "Mozilla/5.0 (compatible; job-dashboard/1.0)"}
MOTS_STAGE = ("stage", "stagiaire", "intern", "internship")
DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _page(start):
    r = requests.get(URL, params={"start": start} if start else None,
                     headers=ENTETES, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def _bloc(lien):
    """Remonte du lien jusqu'au bloc qui contient la date de cette offre seule."""
    bloc = lien
    for _ in range(5):
        bloc = bloc.parent
        if bloc is None:
            return None
        nb_liens = len([a for a in bloc.find_all("a", href=True)
                        if "/offre-d-emploi/" in a["href"]])
        if nb_liens > 1:          # on est monté trop haut : plusieurs offres mélangées
            return None
        if DATE.search(bloc.get_text(" ", strip=True)):
            return bloc
    return None


def _lire_page(soupe):
    offres = []
    for lien in soupe.find_all("a", href=True):
        href = lien["href"]
        if "/offre-d-emploi/" not in href:
            continue
        titre = lien.get_text(" ", strip=True)
        if not titre:
            continue
        url = href if href.startswith("http") else BASE + href

        entreprise, lieu, publiee = "", "", ""
        bloc = _bloc(lien)
        if bloc is not None:
            textes = [t for t in bloc.stripped_strings
                      if t != titre and not DATE.fullmatch(t)]
            if textes:
                entreprise = textes[0]
            if len(textes) > 1:
                lieu = textes[1]
            m = DATE.search(bloc.get_text(" ", strip=True))
            if m:
                publiee = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

        offres.append(Offer(title=titre, company=entreprise or "Cabinet (voir l'offre)",
                            url=url, source="consultor", location=lieu,
                            published=publiee, contract="stage"))
    return offres


def fetch(cfg):
    """Renvoie les offres de STAGE de Consultor (les autres postes sont ignorés)."""
    vues, resultat = set(), []
    for i in range(MAX_PAGES):
        offres = _lire_page(_page(i * PAS))
        nouvelles = [o for o in offres if o.url not in vues]
        if not nouvelles:
            break
        for o in nouvelles:
            vues.add(o.url)
            if any(m in o.title.lower() for m in MOTS_STAGE):
                resultat.append(o)
        time.sleep(1)       # on ménage le site
    return resultat
