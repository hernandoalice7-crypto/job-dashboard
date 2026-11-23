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

# Recherches générales par mots-clés (français et anglais)
MOTS = [
    "stage consultant stratégie",
    "stagiaire consultant",
    "strategy consulting intern",
    "corporate strategy intern",
    "strategy analyst intern",
    "stage direction de la stratégie",
    "stage chargé de mission stratégie",
    "stage corporate development",
    "stage stratégie et développement",
    "stage stratégie d'entreprise",
    "stage conseil en transformation",
    "transformation consultant intern",
    "stage PMO conduite du changement",
    "stage due diligence transaction services",
    "stage M&A private equity",
    "stage ESG stratégie durable",
    "sustainability strategy intern",
    "stage data strategy digital",
    "stage conseil interne",
]
LIEUX = ["Paris, France", "Lyon, France", "Lille, France", "Suisse"]
PAGES = 2          # 2 pages de 25 résultats par recherche générale
PAS = 25
PAUSE = 2          # secondes entre deux requêtes (on ménage le site)


class Bloque(Exception):
    pass


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


def _requete(mot, lieu, page):
    params = {
        "keywords": mot,
        "location": lieu,
        "f_TPR": "r2592000",    # publiées depuis 30 jours
        "f_JT": "I",            # stages
        "start": page * PAS,
    }
    r = requests.get(URL, params=params, headers=ENTETES, timeout=30)
    if r.status_code != 200:
        raise Bloque(f"code {r.status_code}")
    time.sleep(PAUSE)
    return _lire(r.text)


def fetch(cfg):
    # Liste des recherches : (mots-clés, lieu, nombre de pages)
    recherches = [(mot, lieu, PAGES) for mot in MOTS for lieu in LIEUX]
    # Une recherche par entreprise de config.yaml (entreprises_linkedin)
    for ent in cfg.get("entreprises_linkedin") or []:
        recherches.append((f"stage stratégie {ent}", "France", 1))

    vues, resultat = set(), []
    try:
        for mot, lieu, pages in recherches:
            for page in range(pages):
                offres = _requete(mot, lieu, page)
                if not offres:
                    break
                for o in offres:
                    if o.url not in vues:
                        vues.add(o.url)
                        resultat.append(o)
    except Bloque as e:
        if not resultat:       # bloqué dès le début : on signale l'erreur
            raise RuntimeError(f"LinkedIn bloque les requêtes ({e})")
        # bloqué en cours de route : on garde ce qu'on a déjà trouvé
    return resultat
