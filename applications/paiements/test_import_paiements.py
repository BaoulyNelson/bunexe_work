import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from .models import ModePaiement, Tarif


class ImportPaiementsTests(TestCase):
    def test_imports_modes_and_tarifs_repeatedly_without_duplicates(self):
        ModePaiement.objects.create(
            code="moncash",
            libelle="Ancien MonCash",
            logo="paiements/logos/moncash.png",
            actif=False,
            fournisseur="local",
        )
        with tempfile.TemporaryDirectory() as directory:
            modes_path = Path(directory) / "modepaiement.csv"
            tarifs_path = Path(directory) / "paiements_tarif.csv"
            modes_path.write_text(
                "id,code,libelle,logo,actif,gratuit,fournisseur\n"
                "1,sevis-gratis,SÈVIS GRATIS,,True,True,local\n"
                "2,moncash,MonCash,,False,False,moncash\n",
                encoding="utf-8",
            )
            tarifs_path.write_text(
                "id,type_document,prix,devise,actif\n"
                "1,releve,150.00,HTG,True\n"
                "2,certificat,250.00,HTG,True\n"
                "3,releve_certificat,400.00,HTG,True\n",
                encoding="utf-8",
            )

            for _ in range(2):
                call_command(
                    "import_paiements",
                    str(modes_path),
                    str(tarifs_path),
                    stdout=StringIO(),
                )

        self.assertEqual(ModePaiement.objects.count(), 2)
        self.assertEqual(Tarif.objects.count(), 3)
        moncash = ModePaiement.objects.get(code="moncash")
        self.assertEqual(moncash.libelle, "MonCash")
        self.assertEqual(moncash.logo.name, "paiements/logos/moncash.png")
        self.assertFalse(moncash.actif)
        self.assertTrue(ModePaiement.objects.get(code="sevis-gratis").gratuit)
        self.assertEqual(
            str(Tarif.objects.get(type_document="certificat").prix), "250.00"
        )
