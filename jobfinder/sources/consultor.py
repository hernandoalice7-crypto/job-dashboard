"""Source : offres de stage sur Consultor (consultor.fr)."""

import re
import time
import unicodedata

import requests
from bs4 import BeautifulSoup

from jobfinder.models import Offer

BASE = "https://www.consultor.fr"
URL = BASE + "/carrieres/offre-d-emploi"
PAS = 15              # nombre d'offres par page chez Consultor
MAX_PAGES = 8         # sécurité : jamais plus de 8 pages
ENTETES = {"User-Agent": "Mozilla/5.0 (compatible; job-dashboard/1.0)"}
MOTS_STAGE = ("stage", "stagiaire", "intern", "internship")
DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
MOIS = {"janvier": "01", "fevrier": "02", "mars": "03", "avril": "04",
        "mai": "05", "juin": "06", "juillet": "07"}
DEBUT = re.compile(r"(janvier|fevrier|mars|avril|mai|juin|juillet)\s+2027")
INUTILES = {"voir l'offre", "en savoir plus", "stage", "entreprise", "postuler"}


def _sans_accents(texte):
    texte = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in texte if not unicodedata.combining(c)).lower()


def _get(url, params=None):
    r = requests.get(url, params=params, headers=ENTETES, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def _hrefs(bloc):
    return {a["href"] for a in bloc.find_all("a", href=True)
            if "/offre-d-emploi/" in a["href"]}


def _bloc(lien):
    """Remonte jusqu'au bloc qui contient la date de CETTE offre seule."""
    bloc = lien
    for _ in range(6):
        bloc = bloc.parent
        if bloc is None:
            return None
        if len(_hrefs(bloc)) > 1:      # plusieurs offres mélangées : trop haut
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
        if not titre or titre.lower() in INUTILES:
            continue
        url = href if href.startswith("http") else BASE + href

        entreprise, lieu, publiee = "", "", ""
        bloc = _bloc(lien)
        if bloc is not None:
            textes = [t.strip() for t in bloc.stripped_strings
                      if t.strip() != titre and not DATE.fullmatch(t.strip())
                      and t.strip().lower() not in INUTILES]
            if textes:
                entreprise = textes[0]
            if len(textes) > 1:
                lieu = textes[1]
            m = DATE.search(bloc.get_text(" ", strip=True))
            if m:
                publiee = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

        offres.append(Offer(title=titre, company=entreprise, url=url,
                            source="consultor", location=lieu,
                            published=publiee, contract="stage"))
    return offres


def _completer(o):
    """Lit la page de l'offre pour retrouver ce qui manque :
    cabinet, lieu, date de publication, description et date de début."""
    try:
        soupe = _get(o.url)
    except Exception:
        return
    h1 = soupe.find("h1")

    # Cabinet : début du <title> si le reste ressemble au titre de l'offre
    if not o.company and soupe.title:
        morceaux = soupe.title.get_text(strip=True).split(" - ", 1)
        if len(morceaux) == 2 and len(morceaux[1]) >= 12:
            if _sans_accents(morceaux[1])[:12] in _sans_accents(o.title):
                o.company = morceaux[0].strip()

    if h1 is not None:
        # Date de publication : juste avant le titre
        if not o.published:
            for t in h1.find_all_previous(string=DATE, limit=1):
                m = DATE.search(t)
                o.published = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        # Lieu : premier court texte après le titre
        suite = [t.strip() for t in h1.find_all_next(string=True, limit=300)
                 if t.strip()]
        if not o.location and suite and len(suite[0]) < 60:
            o.location = suite[0]
        # Description : jusqu'à « Catégorie »
        morceaux = []
        for t in suite[1:]:
            if t == "Catégorie":
                break
            morceaux.append(t)
        o.description = " ".join(morceaux)[:4000]

    # Date de début, si l'offre indique « mars 2027 », « avril 2027 »...
    if not o.start_date:
        m = DEBUT.search(_sans_accents(o.description))
        if m:
            o.start_date = "2027-" + MOIS[m.group(1)]


def fetch(cfg):
    """Renvoie les offres de STAGE de Consultor (les autres postes sont ignorés)."""
    vues, stages = set(), []
    for i in range(MAX_PAGES):
        offres = _lire_page(_get(URL, {"start": i * PAS} if i else None))
        nouvelles = [o for o in offres if o.url not in vues]
        if not nouvelles:
            break
        for o in nouvelles:
            vues.add(o.url)
            if any(m in o.title.lower() for m in MOTS_STAGE):
                stages.append(o)
        time.sleep(1)       # on ménage le site

    for o in stages:        # une requête par offre, avec une pause
        if not o.company or not o.location or not o.published or not o.description:
            _completer(o)
            time.sleep(1)
        if not o.company:
            o.company = "Cabinet (voir l'offre)"
    return stages
