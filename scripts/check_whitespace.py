"""Flag large bottom gaps in the rendered text area for visual review.

Headers, footers and the normal bottom margin are excluded. Rendered ink
includes vector diagrams and rules, not just extractable text. This is a
screening check: a large display, a table or a chapter ending can justify a
gap. Front matter is every page before the arabic numbering starts.
"""
import hashlib
from pathlib import Path

import fitz
from PIL import Image
from pypdf import PdfReader

from project import layout_settings

ROOT = Path(__file__).resolve().parents[1]
CONFIG = layout_settings(ROOT)
MARGIN_PT = CONFIG["margin_mm"] * 72 / 25.4
THRESHOLD_PT = CONFIG["bottom_gap_threshold_pt"]


def body_metrics(page):
    area = fitz.Rect(0, MARGIN_PT, page.rect.width,
                     page.rect.height - MARGIN_PT)
    scale = CONFIG["render_scale"]
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=area,
                          colorspace=fitz.csGRAY, alpha=False)
    ink = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    bounds = ink.point(
        lambda value: 255 if value < CONFIG["ink_threshold"] else 0).getbbox()
    bottom = (pix.y + bounds[3]) / scale if bounds else area.y0
    return {
        'gap_pt': round(max(0, area.y1 - bottom), 1),
        'body_text': page.get_text('text', clip=area, sort=True).strip(),
    }


def check_whitespace(pdf, bookmarks):
    pdf = Path(pdf)
    with fitz.open(pdf) as doc:
        metrics = [body_metrics(page) for page in doc]
    # Not PyMuPDF's Page.get_label(): its parser reads the optional
    # "/Type /PageLabel" that Typst writes as a prefix ("ageLabel1").
    labels = PdfReader(pdf).page_labels
    chapter_starts = {b['pdf_page']: b['title'] for b in bookmarks
                      if b['depth'] == 0}
    first_text = next((i + 1 for i, label in enumerate(labels)
                       if label.isdecimal()), len(labels) + 1)
    pages = []
    for i, metric in enumerate(metrics):
        number = i + 1
        following = metrics[i + 1] if i + 1 < len(metrics) else None
        row = {'pdf_page': number, 'page_label': labels[i],
               'gap_pt': metric['gap_pt']}
        if number < first_text:
            row['classification'] = 'front matter'
        elif number == len(metrics):
            row['classification'] = 'end of document'
        elif (number + 1 in chapter_starts
              and (number in chapter_starts
                   or metric['gap_pt'] < CONFIG['short_spill_threshold_pt'])):
            row['classification'] = 'before chapter or major division'
            row['next_division'] = chapter_starts[number + 1]
        elif metric['gap_pt'] < THRESHOLD_PT:
            row['classification'] = 'below screening threshold'
        else:
            row['classification'] = 'needs visual review'
            row['body_tail'] = metric['body_text'][-500:]
            row['next_body_head'] = following['body_text'][:500]
        pages.append(row)
    pending = [p['pdf_page'] for p in pages
               if p['classification'] == 'needs visual review']
    return {
        'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
        'status': 'needs_visual_review' if pending else 'passed',
        'advisory': True,
        'pages_checked': len(pages),
        'threshold_pt': THRESHOLD_PT,
        'scope': ('Bottom whitespace inside the text area, measured from '
                  'rendered ink. Normal margins, front matter and ordinary '
                  'chapter endings excluded; very short spill pages still '
                  'require review. Does not replace full visual QA.'),
        'pages_requiring_review': pending,
        'pages': pages,
    }
