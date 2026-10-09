from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

CANDIDATE_CODE_PATTERN = r"\A(?:0[1-9]|10)[0-9]{8}\Z"
CANDIDATE_CODE_VALIDATOR = RegexValidator(
    regex=CANDIDATE_CODE_PATTERN,
    message=_("Le matricule doit contenir 10 chiffres et commencer par 01 à 10."),
)


class Candidat(models.Model):
    class TypeResultat(models.TextChoices):
        BAC_UNIQUE = "bac_unique", _("BAC UNIQUE")
        PERM_NS4 = "perm_ns4", _("PERM. NS4")
        PERM_PHILO = "perm_philo", _("PERM. PHILO")
        NEUVIEME_AF = "9e_af", _("9ÈME A.F")

    class Statut(models.TextChoices):
        ADMIS = "admis", _("Admis")
        ECHOUE = "echoue", _("Échoué")

    type_resultat = models.CharField(
        max_length=16,
        choices=TypeResultat.choices,
        default=TypeResultat.BAC_UNIQUE,
        db_index=True,
    )
    annee = models.PositiveSmallIntegerField(db_index=True)
    code = models.CharField(max_length=24, validators=[CANDIDATE_CODE_VALIDATOR])
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=120, blank=True)
    telephone = models.CharField(max_length=32, blank=True)
    total_points = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    total_sur = models.PositiveSmallIntegerField(default=1900)
    mention = models.CharField(max_length=60, blank=True)
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.ECHOUE
    )
    serie = models.CharField(max_length=40, blank=True)
    ecole = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["annee", "nom", "prenom"]
        constraints = [
            models.UniqueConstraint(
                fields=["annee", "code"], name="unique_candidat_annee_code"
            )
        ]
        indexes = [models.Index(fields=["annee", "nom", "prenom"])]

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.annee} / {self.code})"

    @property
    def mention_affichee(self):
        if self.statut == self.Statut.ECHOUE:
            return self.get_statut_display()
        return self.mention or self.get_statut_display()

    def save(self, *args, **kwargs):
        self.statut = (
            self.Statut.ADMIS
            if self.total_sur and self.total_points * 2 >= self.total_sur
            else self.Statut.ECHOUE
        )
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"statut"}
        super().save(*args, **kwargs)


class NoteMatiere(models.Model):
    candidat = models.ForeignKey(
        Candidat, on_delete=models.CASCADE, related_name="notes_matieres"
    )
    matiere = models.CharField(max_length=100)
    note = models.PositiveSmallIntegerField()
    coefficient = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidat", "matiere"],
                name="unique_matiere_par_candidat",
            )
        ]

    def __str__(self):
        return f"{self.candidat.code} - {self.matiere}: {self.note}/{self.coefficient}"

    @property
    def is_failing(self):
        return self.note * 2 < self.coefficient


class MatiereProgramme(models.Model):
    examen = models.CharField(max_length=16)
    serie = models.CharField(max_length=40, blank=True)
    matiere = models.CharField(max_length=180)
    coefficient = models.PositiveSmallIntegerField()
    ordre = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ("examen", "serie", "ordre", "matiere")
        constraints = [
            models.UniqueConstraint(
                fields=("examen", "serie", "matiere"),
                name="unique_matiere_programme",
            )
        ]
        verbose_name = "matière du programme"
        verbose_name_plural = "matières du programme"

    def __str__(self):
        serie = f" · {self.serie}" if self.serie else ""
        return f"{self.examen}{serie} · {self.matiere} ({self.coefficient})"
