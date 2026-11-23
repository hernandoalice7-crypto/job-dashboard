"""Source : pages carrières d'entreprises (Greenhouse, Lever, Ashby, SmartRecruiters).
Les entreprises à suivre sont listées dans config.yaml, section entreprises_suivies."""

import html
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from jobfinder.models import Offer

ENTETES = {"User-Agent": "Mozilla/5.0 (compatible; job-dashboard/1.0)"}
STAGE = re.compile(r"\b(stage|stagiaire|intern|internship)\b", re.IGNORECASE)
PAUSE = 1


def _get(url, params=None):
    r = requests.get(url, params=params, headers=ENTETES, timeout=30)
    r.raise_for_status()
    return r.json()


def _est_stage(*textes):
    return bool(STAGE.search(" ".join(t or "" for t in textes)))


def _texte(contenu):
    """Transforme du HTML en texte simple."""
    brut = html.unescape(contenu or "")
    return BeautifulSoup(brut, "html.parser").get_text(" ", strip=True)[:4000]


def _entreprise(entree):
    """'doctolib' ou 'doctolib|Doctolib' (identifiant | nom affiché)."""
    texte = str(entree)
    if "|" in texte:
        ident, nom = texte.split("|", 1)
        return ident.strip(), nom.strip()
    return texte.strip(), texte.strip().capitalize()


def _greenhouse(ident, nom):
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{ident}/jobs",
                {"content": "true"})
    offres = []
    for j in data.get("jobs", []):
        titre = j.get("title", "")
        if not _est_stage(titre):
            continue
        offres.append(Offer(
            title=titre, company=nom, url=j.get("absolute_url", ""),
            source="carrieres", contract="stage",
            location=(j.get("location") or {}).get("name", ""),
            published=(j.get("first_published") or j.get("updated_at") or "")[:10],
            description=_texte(j.get("content"))))
    return offres


def _lever(ident, nom):
    data = _get(f"https://api.lever.co/v0/postings/{ident}", {"mode": "json"})
    offres = []
    for j in data:
        titre = j.get("text", "")
        cat = j.get("categories") or {}
        if not _est_stage(titre, cat.get("commitment")):
            continue
        cree = j.get("createdAt")
        publie = (datetime.fromtimestamp(cree / 1000, tz=timezone.utc).date().isoformat()
                  if cree else "")
        offres.append(Offer(
            title=titre, company=nom, url=j.get("hostedUrl", ""),
            source="carrieres", contract="stage",
            location=cat.get("location", ""), published=publie,
            description=(j.get("descriptionPlain") or "")[:4000]))
    return offres


def _ashby(ident, nom):
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{ident}")
    offres = []
    for j in data.get("jobs", []):
        titre = j.get("title", "")
        if not _est_stage(titre, j.get("employmentType")):
            continue
        offres.append(Offer(
            title=titre, company=nom, url=j.get("jobUrl", ""),
            source="carrieres", contract="stage",
            location=j.get("location", "") or "",
            published=(j.get("publishedAt") or "")[:10],
            description=(j.get("descriptionPlain") or "")[:4000]))
    return offres


def _smartrecruiters(ident, nom):
    offres, vues = [], set()
    for mot in ("stage", "intern"):
        data = _get(f"https://api.smartrecruiters.com/v1/companies/{ident}/postings",
                    {"q": mot, "limit": 100})
        for j in data.get("content", []):
            titre = j.get("name", "")
            if j.get("id") in vues:
                continue
            emploi = (j.get("typeOfEmployment") or {}).get("label", "")
            if not _est_stage(titre, emploi):
                continue
            vues.add(j.get("id"))
            lieu = j.get("location") or {}
            offres.append(Offer(
                title=titre, company=nom,
                url=f"https://jobs.smartrecruiters.com/{ident}/{j.get('id')}",
                source="carrieres", contract="stage",
                location=", ".join(x for x in (lieu.get("city"), (lieu.get("country") or "").upper()) if x),
                published=(j.get("releasedDate") or "")[:10]))
        time.sleep(PAUSE)
    return offres


PLATEFORMES = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "ashby": _ashby,
    "smartrecruiters": _smartrecruiters,
}


def fetch(cfg):
    suivies = cfg.get("entreprises_suivies") or {}
    offres, erreurs = [], []
    for plateforme, lire in PLATEFORMES.items():
        for entree in suivies.get(plateforme) or []:
            ident, nom = _entreprise(entree)
            try:
                offres.extend(lire(ident, nom))
            except Exception as e:
                erreurs.append(f"{plateforme}/{ident} ({type(e).__name__})")
            time.sleep(PAUSE)
    if erreurs:
        print("[carrieres] entreprises en erreur :", "; ".join(erreurs))
        if not offres:
            raise RuntimeError("Aucune entreprise lisible : " + "; ".join(erreurs[:3]))
    return offres
