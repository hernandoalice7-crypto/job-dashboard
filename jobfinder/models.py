"""Définition d'une offre : le format commun à toutes les sources."""

import hashlib
from dataclasses import dataclass, field


@dataclass
class Offer:
    # --- Informations lues sur le site d'offres ---
    title: str                      # intitulé du poste
    company: str                    # entreprise ou cabinet
    url: str                        # lien vers l'offre
    source: str                     # nom de la source (ex. "consultor")
    location: str = ""              # ville ou lieu, si indiqué
    published: str = ""             # date de publication, format AAAA-MM-JJ ("" si inconnue)
    start_date: str = ""            # date de début du stage, format AAAA-MM-JJ ("" si inconnue)
    contract: str = ""              # stage, vie, graduate... ("" si inconnu)
    duration_months: int = 0        # durée en mois (0 si inconnue)
    salary: str = ""                # rémunération affichée, en texte libre
    description: str = ""           # texte de l'offre, si disponible

    # --- Informations calculées par le programme ---
    score: int = 0                  # note sur 100
    reasons: list = field(default_factory=list)   # pourquoi cette note
    badges: list = field(default_factory=list)    # NOUVEAU, DATE ?, AVANT FIN D'EXAMS...
    is_new: bool = False            # jamais vue lors d'un passage précédent

    @property
    def id(self) -> str:
        """Identifiant unique de l'offre, calculé à partir de son lien.
        Sert à reconnaître une offre déjà vue."""
        return hashlib.sha1(self.url.strip().lower().encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Transforme l'offre en dictionnaire, pour l'écrire dans la page."""
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "source": self.source,
            "location": self.location,
            "published": self.published,
            "start_date": self.start_date,
            "contract": self.contract,
            "duration_months": self.duration_months,
            "salary": self.salary,
            "score": self.score,
            "reasons": self.reasons,
            "badges": self.badges,
            "is_new": self.is_new,
        }
