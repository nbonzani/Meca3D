# SPDX-License-Identifier: GPL-3.0-or-later
"""Met à jour la table des matières du guide Word et l'exporte en PDF (Microsoft Word requis).

Usage : uv run --with pywin32 python docs/guide/exporter_pdf.py
Le document est ouvert en lecture seule puis réenregistré sous un nom temporaire : l'ouverture en
écriture, comme `Fields.Update()`, bloque Word sur certains postes. PAGE et NUMPAGES se mettent à
jour d'eux-mêmes à l'export.
"""

import shutil
import tempfile
from pathlib import Path

import win32com.client  # type: ignore[import-not-found]

ICI = Path(__file__).resolve().parent
DOCX = ICI / "Meca3D_Guide_utilisateur.docx"
PDF = DOCX.with_suffix(".pdf")
FORMAT_DOCX, FORMAT_PDF, SANS_ENREGISTRER = 16, 17, 0


def main() -> None:
    temporaire = Path(tempfile.gettempdir()) / "Meca3D_Guide_maj.docx"
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(str(DOCX), False, True, False)
        for i in range(1, doc.TablesOfContents.Count + 1):
            doc.TablesOfContents.Item(i).Update()
        doc.SaveAs2(str(temporaire), FORMAT_DOCX)
        doc.ExportAsFixedFormat(str(PDF), FORMAT_PDF)
        doc.Close(False)
    finally:
        word.Quit(SANS_ENREGISTRER)
    shutil.move(temporaire, DOCX)
    print(f"Guide et PDF mis à jour : {DOCX.name}, {PDF.name}")


if __name__ == "__main__":
    main()
