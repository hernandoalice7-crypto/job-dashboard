"""Source : LinkedIn (recherche publique, sans compte)."""

import time

import requests
from bs4 import BeautifulSoup

from jobfinder.models import Offer

URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
ENTETES = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

# Mots-clés tirés de tes réponses (français et anglais)
MOTS = [
    "stage consultant stratégie",
    "stagiaire consultant",
    "stage conseil en transformation",
    "strategy consulting intern",
    "corporate strategy intern",
    "stage stratégie",
]
LIEUX = ["Paris, France", "Lyon, France", "Lille, France", "Suisse"]
PAGES = 2          # 2 pages de 25 résultats par recherche
PAS = 25
PAUSE = 2          # secondes entre deux requêtes (on ménage le site)


def _lire(html):
    offres = []
    for li in BeautifulSoup(html, "html.parser").find_all("li"):
        lien = li.find("a", class_="base-card__full-link")
        titre = li.find("h3")
        if lien is None or titre is None:
            continue
        entreprise = li.find("h4")
        lieu = li.find("span", class_="job-search-card__location")
        date = li.find("time")
        offres.append(Offer(
            title=titre.get_text(" ", strip=True),
            company=entreprise.get_text(" ", strip=True) if entreprise else "",
            url=lien["href"].split("?")[0],
            source="linkedin",
            location=lieu.get_text(" ", strip=True) if lieu else "",
            published=date.get("datetime", "") if date else "",
            contract="stage",
        ))
    return offres


def fetch(cfg):
    vues, resultat = set(), []
    for mot in MOTS:
        for lieu in LIEUX:
            for page in range(PAGES):
                params = {
                    "keywords": mot,
                    "location": lieu,
                    "f_TPR": "r2592000",    # publiées depuis 30 jours
                    "f_JT": "I",            # stages
                    "start": page * PAS,
                }
                r = requests.get(URL, params=params, headers=ENTETES, timeout=30)
                if r.status_code != 200:
                    if not resultat:
                        raise RuntimeError(
                            f"LinkedIn bloque les requêtes (code {r.status_code})")
                    return resultat      # bloqué en cours de route : on garde l'acquis
                offres = _lire(r.text)
                time.sleep(PAUSE)
                if not offres:
                    break
                for o in offres:
                    if o.url not in vues:
                        vues.add(o.url)
                        resultat.append(o)
    return resultat
