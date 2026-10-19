"""Filtres et score sur 100. Tout est réglé dans config.yaml."""

import calendar
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

# Mots qui indiquent qu'une langue est un « plus » et non une obligation
LANGUE_SOUPLE = ("un plus", "atout", "apprecie", "bonus", "nice to have", "a plus")

# Mots génériques du conseil dans un titre (second choix si rien d'autre ne correspond)
MOTS_CONSEIL = ["consultant", "consultante", "consulting", "conseil"]


def norm(texte):
    """Minuscules, sans accents, pour comparer facilement."""
    texte = (texte or "").replace("’", "'")
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return texte.lower()


def has_word(texte, mot):
    """Vrai si le mot ou l'expression apparaît en entier dans le texte."""
    motif = r"(?<![a-z0-9])" + re.escape(norm(mot)) + r"(?![a-z0-9])"
    return re.search(motif, texte) is not None


def parse_day(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def exige_langue(texte, mots):
    """Vrai si une langue rédhibitoire est exigée (et pas seulement un « plus »)."""
    for mot in mots:
        motif = r"(?<![a-z0-9])" + re.escape(norm(mot)) + r"(?![a-z0-9])"
        for m in re.finditer(motif, texte):
            apres = texte[m.end(): m.end() + 40]
            avant = texte[max(0, m.start() - 40): m.start()]
            if any(k in apres or k in avant for k in LANGUE_SOUPLE):
                continue
            return True
    return False


def verifier_dates(o, cfg):
    """Renvoie (raison_de_retrait, part_des_points, badge, texte_explication)."""
    d = cfg["dates"]
    dmax = parse_day(d["debut_max"])
    ex1, ex2 = parse_day(d["avant_examens_du"]), parse_day(d["avant_examens_au"])
    s = (o.start_date or "").strip()
    jour = parse_day(s)

    # Date au format AAAA-MM (mois seulement)
    if jour is None and len(s) == 7:
        premier = parse_day(s + "-01")
        if premier is not None:
            dernier = premier.replace(day=calendar.monthrange(premier.year, premier.month)[1])
            if dernier < ex1:
                return "date_trop_tot", 0, None, None
            if premier > dmax:
                return "date_trop_tard", 0, None, None
            if premier <= ex2 and dernier >= ex1:
                return None, 8 / 15, "VÉRIFIER DATE", "Début dans le mois de tes examens : date exacte à vérifier"
            jour = premier

    if jour is None:
        if d.get("garder_si_date_inconnue", True):
            return None, 5 / 15, "DATE ?", "Date de début non indiquée"
        return "date_inconnue", 0, None, None

    if jour < ex1:
        return "date_trop_tot", 0, None, None
    if jour > dmax:
        return "date_trop_tard", 0, None, None
    if jour <= ex2:
        return None, 8 / 15, "AVANT FIN D'EXAMS", "Début avant la fin des examens"
    if jour.month <= 5:
        return None, 1.0, None, "Début entre fin mars et mai"
    if jour.month == 6:
        return None, 12 / 15, None, "Début en juin"
    return None, 10 / 15, None, "Début en juillet"


def verifier_lieu(o, cfg):
    """Renvoie (raison_de_retrait, part_des_points, badge, texte_explication)."""
    L = cfg["lieux"]
    lieu = norm(o.location)
    if not lieu.strip():
        if L.get("garder_si_lieu_inconnu", True):
            return None, 5 / 15, "LIEU ?", "Lieu non indiqué"
        return "lieu_inconnu", 0, None, None

    def trouve(liste):
        return any(has_word(lieu, v) for v in liste or [])

    paris, lyon_lille, suisse = trouve(L.get("paris")), trouve(L.get("lyon_lille")), trouve(L.get("suisse"))
    exclu = trouve(L.get("exclus"))

    if exclu and not (paris or lyon_lille or suisse):
        return "lieu_exclu", 0, None, None
    if paris:
        return None, 1.0, None, "Paris / Île-de-France"
    if lyon_lille:
        return None, 10 / 15, None, "Lyon ou Lille"
    if suisse:
        return None, 8 / 15, None, "Suisse"
    if L.get("garder_autres_villes", True):
        return None, 3 / 15, "AUTRE VILLE", "Autre ville que tes préférées"
    return "lieu_hors_zone", 0, None, None


def points(poids, part):
    return round(poids * part)


def evaluer(o, cfg, aujourdhui):
    """Filtre et note une offre. Renvoie None si elle est gardée,
    sinon la raison pour laquelle elle est retirée."""
    M, W = cfg["metiers"], cfg["score"]
    titre = norm(o.title)
    texte = norm(o.title + " " + o.description)
    o.reasons, o.badges = [], []

    # --- 1. Exclusions directes ---
    if any(has_word(titre, m) for m in M.get("exclus", [])):
        return "mot_exclu_dans_titre"
    exclues = [norm(e) for e in (cfg.get("entreprises_exclues") or [])]
    if norm(o.company) in exclues:
        return "entreprise_exclue"
    if exige_langue(texte, cfg["langues"].get("rédhibitoires", [])):
        return "langue_exigee"

    # --- 2. Contrat et durée ---
    duree_max = cfg["contrat"].get("duree_max_mois", 6)
    if o.duration_months and o.duration_months > duree_max:
        return "duree_trop_longue"
    acceptes = [norm(t) for t in cfg["contrat"].get("types_acceptes", [])]
    if o.contract and norm(o.contract) not in acceptes:
        return "contrat_refuse"

    # --- 3. Métier ---
    if any(has_word(titre, m) for m in M.get("prioritaires", [])):
        part_metier, txt_metier = 1.0, "Métier prioritaire"
    elif any(has_word(titre, m) for m in M.get("acceptables", [])) or \
            any(has_word(titre, m) for m in MOTS_CONSEIL):
        part_metier, txt_metier = 20 / 35, "Métier acceptable"
    else:
        return "hors_sujet"

    # --- 4. Dates et lieu ---
    raison, part_date, badge_date, txt_date = verifier_dates(o, cfg)
    if raison:
        return raison
    raison, part_lieu, badge_lieu, txt_lieu = verifier_lieu(o, cfg)
    if raison:
        return raison

    # --- 5. Score ---
    total = 0

    p = points(W["metier"], part_metier)
    total += p
    o.reasons.append(f"{txt_metier} (+{p})")

    if any(k in texte for k in ("fin d'etudes", "fin d'etude", "final year", "end of studies")):
        part_contrat, txt_contrat = 1.0, "Stage de fin d'études"
    elif norm(o.contract) == "stage" or any(has_word(texte, k) for k in ("stage", "stagiaire", "intern", "internship")):
        part_contrat, txt_contrat = 12 / 15, "Stage"
    else:
        part_contrat, txt_contrat = 8 / 15, "Autre contrat"
    p = points(W["contrat"], part_contrat)
    total += p
    o.reasons.append(f"{txt_contrat} (+{p})")

    p = points(W["date_debut"], part_date)
    total += p
    o.reasons.append(f"{txt_date} (+{p})")
    if badge_date:
        o.badges.append(badge_date)

    p = points(W["lieu"], part_lieu)
    total += p
    o.reasons.append(f"{txt_lieu} (+{p})")
    if badge_lieu:
        o.badges.append(badge_lieu)

    # Fraîcheur de l'offre
    pub = parse_day(o.published)
    if pub is None:
        part_f, txt_f = 3 / 10, "Date de publication inconnue"
    else:
        age = (aujourdhui - pub).days
        if age <= 7:
            part_f, txt_f = 1.0, "Publiée il y a moins d'une semaine"
        elif age <= 30:
            part_f, txt_f = 7 / 10, "Publiée il y a moins d'un mois"
        elif age <= 90:
            part_f, txt_f = 4 / 10, "Publiée il y a moins de 3 mois"
        else:
            part_f, txt_f = 2 / 10, "Publiée il y a plus de 3 mois"
    p = points(W["fraicheur"], part_f)
    total += p
    o.reasons.append(f"{txt_f} (+{p})")

    # Mots bonus
    trouves = [m for m in M.get("bonus", []) if has_word(texte, m)]
    if trouves:
        p = W["mots_bonus"]
        total += p
        o.reasons.append(f"Mots bonus : {', '.join(trouves[:3])} (+{p})")

    # Salaire affiché (bonus seulement)
    if o.salary:
        p = W["salaire_affiche"]
        total += p
        o.reasons.append(f"Salaire affiché (+{p})")

    o.score = max(0, min(100, total))
    return None


def traiter(offres, cfg):
    """Filtre et note toutes les offres.
    Renvoie (offres_gardées_triées, statistiques_par_source)."""
    aujourdhui = datetime.now(ZoneInfo("Europe/Paris")).date()
    gardees, stats = [], {}
    for o in offres:
        s = stats.setdefault(o.source, {"trouvees": 0, "gardees": 0, "retirees": {}})
        s["trouvees"] += 1
        raison = evaluer(o, cfg, aujourdhui)
        if raison:
            s["retirees"][raison] = s["retirees"].get(raison, 0) + 1
        else:
            s["gardees"] += 1
            gardees.append(o)
    gardees.sort(key=lambda o: (-o.score, o.company.lower()))
    return gardees, stats
