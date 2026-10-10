"""Isolated PDFium rendering so OCR can enforce a subprocess deadline."""
import sys

import pypdfium2 as pdfium


def main():
    document = pdfium.PdfDocument(sys.argv[1])
    try:
        page = document[int(sys.argv[2])]
        try:
            bitmap = page.render(scale=180 / 72)
            try:
                bitmap.to_pil().save(sys.argv[3])
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()


if __name__ == "__main__":
    main()
