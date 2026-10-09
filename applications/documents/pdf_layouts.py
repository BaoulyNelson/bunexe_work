from io import BytesIO

import qrcode
from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from applications.candidats.models import Candidat

MONTHS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def _today_label():
    today = timezone.localdate()
    return f"{today.day} {MONTHS_FR[today.month - 1]} {today.year}"


def _image_reader(filename):
    image_path = finders.find(f"images/{filename}")
    return ImageReader(image_path) if image_path else None


def _logo_reader():
    return _image_reader("logo.png")


def _draw_logo(pdf, logo, x, y, size):
    if logo:
        pdf.drawImage(
            logo,
            x,
            y,
            width=size,
            height=size,
            preserveAspectRatio=True,
            mask="auto",
        )


def _draw_qr(verification_url):
    image = BytesIO()
    qrcode.make(verification_url).save(image, format="PNG")
    image.seek(0)
    return ImageReader(image)


def _draw_wrapped(pdf, text, x, y, width, font="Helvetica", size=9, leading=12):
    pdf.setFont(font, size)
    for line in simpleSplit(text, font, size, width):
        pdf.drawString(x, y, line)
        y -= leading
    return y


def _draw_certificate(
    pdf, document, qr_image, logo, blason, directeur_signature, chef_service_signature
):
    candidat = document.demande.candidat
    width, height = landscape(A4)
    ink = colors.HexColor("#202b33")
    border = colors.HexColor("#555c59")
    gold = colors.HexColor("#ad985f")

    pdf.setFillColor(colors.HexColor("#fbfaf6"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setStrokeColor(border)
    pdf.setLineWidth(2.2)
    pdf.roundRect(19, 18, width - 38, height - 36, 12, fill=0, stroke=1)
    pdf.setStrokeColor(gold)
    pdf.setLineWidth(0.7)
    pdf.roundRect(27, 26, width - 54, height - 52, 9, fill=0, stroke=1)

    if blason:
        pdf.drawImage(
            blason,
            width / 2 - 48,
            height / 2 - 36,
            width=96,
            height=72,
            mask="auto",
        )

    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(border)
    pdf.roundRect(width / 2 - 118, height - 48, 236, 29, 13, fill=1, stroke=1)
    pdf.setFillColor(ink)
    pdf.setFont("Times-Bold", 13)
    pdf.drawCentredString(width / 2, height - 39, "RÉPUBLIQUE D'HAÏTI")

    _draw_logo(pdf, logo, width / 2 - 35, height - 119, 70)
    pdf.setFillColor(ink)
    pdf.setFont("Times-Roman", 10)
    pdf.drawCentredString(
        width / 2,
        height - 132,
        "MINISTÈRE DE L'ÉDUCATION NATIONALE ET DE LA FORMATION PROFESSIONNELLE",
    )
    pdf.setFont("Times-Bold", 14)
    pdf.drawCentredString(
        width / 2, height - 163, "DIPLÔME DE FIN D'ÉTUDES SECONDAIRES"
    )

    pdf.drawImage(qr_image, 66, height - 262, width=70, height=70, mask="auto")
    name = f"{candidat.prenom} {candidat.nom}"
    name_size = 22
    while (
        name_size > 15 and pdf.stringWidth(name, "Times-Bold", name_size) > width - 170
    ):
        name_size -= 1
    pdf.setFont("Times-Bold", name_size)
    pdf.drawCentredString(width / 2, height - 218, name)

    pdf.setFont("Times-Bold", 10)
    birth = (
        f"né(e) le {candidat.date_naissance:%d/%m/%Y}"
        if candidat.date_naissance
        else ""
    )
    birthplace = f"à {candidat.lieu_naissance}" if candidat.lieu_naissance else ""
    pdf.drawCentredString(
        width / 2, height - 246, "   ·   ".join(filter(None, [birth, birthplace]))
    )
    pdf.drawCentredString(
        width / 2,
        height - 276,
        f"a obtenu son diplôme à la session de juillet {candidat.annee}",
    )
    pdf.setFont("Times-BoldItalic", 17)
    pdf.drawCentredString(
        width / 2,
        height - 310,
        candidat.serie or candidat.get_type_resultat_display(),
    )

    pdf.setFont("Times-Bold", 10)
    pdf.drawString(116, height - 348, f"Numéro d'enregistrement : {candidat.code}")
    pdf.drawRightString(
        width - 106,
        height - 348,
        "Fait à Port-au-Prince, le " + _today_label(),
    )
    pdf.setFont("Times-Bold", 9)
    pdf.drawCentredString(width / 2, 137, "Par délégation du Ministre")
    pdf.drawCentredString(width / 2, 123, "La Direction Générale")

    if directeur_signature:
        pdf.drawImage(directeur_signature, 89, 94, width=130, height=66, mask="auto")
    if chef_service_signature:
        pdf.drawImage(
            chef_service_signature,
            width - 219,
            94,
            width=130,
            height=66,
            mask="auto",
        )

    pdf.setStrokeColor(ink)
    pdf.setLineWidth(0.7)
    pdf.line(72, 88, 236, 88)
    pdf.line(width - 236, 88, width - 72, 88)
    pdf.setFont("Times-Bold", 9)
    pdf.drawCentredString(154, 72, "Le Directeur du Bureau")
    pdf.drawCentredString(154, 60, "National des Examens d'État")
    pdf.drawCentredString(width - 154, 72, "Le Directeur")
    pdf.drawCentredString(width - 154, 60, "de l'Enseignement Secondaire")
    _draw_logo(pdf, logo, width / 2 - 31, 45, 62)

    pdf.saveState()
    pdf.translate(49, height / 2)
    pdf.rotate(90)
    pdf.setFont("Times-Bold", 12)
    pdf.drawCentredString(
        0, 0, f"{candidat.get_type_resultat_display()} {candidat.annee}"
    )
    pdf.restoreState()
    pdf.saveState()
    pdf.translate(width - 49, height / 2)
    pdf.rotate(90)
    pdf.setFont("Times-Bold", 12)
    pdf.drawCentredString(0, 0, "ENSEIGNEMENT SECONDAIRE")
    pdf.restoreState()


def _draw_transcript(
    pdf, document, qr_image, logo, directeur_signature, chef_service_signature
):
    candidat = document.demande.candidat
    width, height = A4
    ink = colors.HexColor("#1d1d1d")
    muted = colors.HexColor("#686868")

    _draw_logo(pdf, logo, width / 2 - 28, height - 79, 56)
    pdf.setFillColor(ink)
    pdf.setFont("Times-Bold", 9)
    pdf.drawCentredString(width / 2, height - 94, "RÉPUBLIQUE D'HAÏTI")
    pdf.setFont("Times-Bold", 10)
    pdf.drawCentredString(width / 2, height - 117, "MINISTÈRE DE L'ÉDUCATION NATIONALE")
    pdf.drawCentredString(width / 2, height - 131, "ET DE LA FORMATION PROFESSIONNELLE")
    pdf.setFont("Times-Bold", 8)
    pdf.drawCentredString(width / 2, height - 149, "DIRECTION GÉNÉRALE")

    pdf.setFont("Times-Italic", 8)
    pdf.setFillColor(muted)
    pdf.drawRightString(width - 38, height - 166, _today_label())
    pdf.setFillColor(ink)
    pdf.setFont("Times-Bold", 12)
    pdf.drawCentredString(width / 2, height - 184, "RELEVÉ DE NOTES")

    birth = (
        f"né(e) le {candidat.date_naissance.day} "
        f"{MONTHS_FR[candidat.date_naissance.month - 1]} "
        f"{candidat.date_naissance.year}"
        if candidat.date_naissance
        else ""
    )
    birthplace = f" à {candidat.lieu_naissance}" if candidat.lieu_naissance else ""
    exam_levels = {
        Candidat.TypeResultat.BAC_UNIQUE: "Secondaire IV",
        Candidat.TypeResultat.PERM_NS4: "Secondaire IV",
    }
    exam_label = candidat.get_type_resultat_display()
    level = exam_levels.get(candidat.type_resultat)
    if level:
        exam_label += f", {level}"
    if candidat.serie:
        exam_label += f" à la série {candidat.serie}"
    intro = (
        f"La Direction Générale du Ministère de l'Éducation Nationale et de la Formation "
        f"Professionnelle certifie que {candidat.nom} {candidat.prenom}"
        f"{', ' + birth if birth else ''}{birthplace}, "
        f"enregistré(e) sous le numéro {candidat.code}, "
        f"a participé aux examens de {exam_label} pour la session de juillet "
        f"{candidat.annee} et a obtenu les notes suivantes :"
    )
    y = _draw_wrapped(pdf, intro, 38, height - 210, width - 76, size=8, leading=11)
    y -= 12
    pdf.setFont("Times-Bold", 11)
    pdf.drawCentredString(width / 2, y, f"Juillet {candidat.annee}")
    y -= 25

    left = 120
    right = width - 105
    pdf.setFont("Times-Bold", 8)
    pdf.drawString(left, y, "MATIÈRES")
    pdf.drawRightString(right, y, "NOTES")
    y -= 9
    if chef_service_signature:
        pdf.drawImage(
            chef_service_signature,
            89,
            106,
            width=86,
            height=44,
            mask="auto",
        )
    if directeur_signature:
        pdf.drawImage(
            directeur_signature,
            width - 175,
            106,
            width=86,
            height=44,
            mask="auto",
        )

    pdf.setStrokeColor(colors.HexColor("#777777"))
    pdf.setLineWidth(0.4)
    pdf.line(left, y, right, y)
    y -= 14

    notes = list(candidat.notes_matieres.all())
    if candidat.type_resultat in {
        Candidat.TypeResultat.PERM_NS4,
        Candidat.TypeResultat.PERM_PHILO,
    }:
        notes = [note for note in notes if note.is_failing]

    pdf.setFont("Times-Roman", 8)
    for note in notes:
        pdf.setFillColor(colors.HexColor("#c33b3b") if note.is_failing else ink)
        pdf.drawString(left, y, note.matiere)
        pdf.drawRightString(right, y, f"{note.note} / {note.coefficient}")
        y -= 15

    if not notes:
        pdf.setFillColor(muted)
        pdf.drawCentredString(width / 2, y, "Détail des matières non disponible")
        y -= 15

    y -= 8
    pdf.setFillColor(ink)
    pdf.setFont("Times-Bold", 9)
    pdf.drawCentredString(
        width / 2,
        y,
        f"{format(candidat.total_points.normalize(), 'f')} sur {candidat.total_sur}",
    )

    pdf.setStrokeColor(colors.HexColor("#777777"))
    pdf.line(45, 104, 220, 104)
    pdf.line(width - 220, 104, width - 45, 104)
    pdf.setFont("Times-Bold", 8)
    pdf.drawCentredString(132, 91, "Chef du Service")
    pdf.drawCentredString(132, 80, "de Certification et d'Équivalence")
    pdf.drawCentredString(width - 132, 91, "Directeur")
    pdf.drawCentredString(width - 132, 80, "Bureau National des Examens d'État")

    pdf.setFillColor(muted)
    pdf.setFont("Times-Roman", 7)
    pdf.drawCentredString(width / 2, 30, f"Vérification : {document.code_verification}")
    pdf.setFillColor(colors.black)
    pdf.drawImage(qr_image, width - 72, 25, width=42, height=42, mask="auto")


def generate_document_pdf(document, verification_url):
    qr_image = _draw_qr(verification_url)
    logo = _logo_reader()
    blason = _image_reader("blason.png")
    directeur_signature = _image_reader("directeur.png")
    chef_service_signature = _image_reader("chef_service.png")
    output = BytesIO()
    if document.type_document == "certificat":
        pdf = canvas.Canvas(output, pagesize=landscape(A4), pageCompression=0)
        _draw_certificate(
            pdf,
            document,
            qr_image,
            logo,
            blason,
            directeur_signature,
            chef_service_signature,
        )
    else:
        pdf = canvas.Canvas(output, pagesize=A4, pageCompression=0)
        _draw_transcript(
            pdf, document, qr_image, logo, directeur_signature, chef_service_signature
        )
    pdf.save()
    return output.getvalue()


def generate_result_ticket_pdf(candidat):
    notes = list(candidat.notes_matieres.all())
    width = 226.77
    height = 250 + len(notes) * 17
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height), pageCompression=0)
    y = height - 24
    pdf.setFont("Times-Bold", 12)
    pdf.drawCentredString(width / 2, y, "RÉSULTAT OFFICIEL")
    y -= 22
    pdf.setFont("Times-Bold", 10)
    pdf.drawCentredString(width / 2, y, candidat.get_type_resultat_display())
    y -= 17
    pdf.setFont("Times-Roman", 8)
    for line in simpleSplit(
        f"{candidat.nom} {candidat.prenom}", "Times-Roman", 8, width - 32
    ):
        pdf.drawCentredString(width / 2, y, line)
        y -= 11
    pdf.drawCentredString(width / 2, y, f"Code : {candidat.code}")
    y -= 13
    pdf.drawCentredString(width / 2, y, f"Session : {candidat.annee}")
    y -= 18
    pdf.setStrokeColor(colors.HexColor("#777777"))
    pdf.line(16, y, width - 16, y)
    y -= 15
    pdf.setFont("Times-Bold", 8)
    pdf.drawString(18, y, "MATIÈRE")
    pdf.drawRightString(width - 18, y, "NOTE / COEF.")
    y -= 12
    pdf.setFont("Times-Roman", 8)
    for note in notes:
        pdf.setFillColor(
            colors.HexColor("#c33b3b") if note.is_failing else colors.black
        )
        pdf.drawString(18, y, note.matiere[:30])
        pdf.drawRightString(width - 18, y, f"{note.note} / {note.coefficient}")
        y -= 17
    if not notes:
        pdf.drawCentredString(width / 2, y, "Détail des matières non disponible")
        y -= 17
    pdf.setFillColor(colors.black)
    y -= 4
    pdf.setStrokeColor(colors.HexColor("#777777"))
    pdf.line(16, y, width - 16, y)
    y -= 17
    pdf.setFont("Times-Bold", 9)
    pdf.drawCentredString(
        width / 2,
        y,
        f"Total : {format(candidat.total_points.normalize(), 'f')} / {candidat.total_sur}",
    )
    y -= 14
    pdf.setFont("Times-Roman", 8)
    pdf.drawCentredString(width / 2, y, candidat.mention_affichee)
    y -= 14
    pdf.drawCentredString(width / 2, y, _today_label())
    pdf.save()
    return output.getvalue()
