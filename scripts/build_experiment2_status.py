"""Render the one-page status from its canonical Markdown source."""
from pathlib import Path
import html
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT_ROOT = Path('/usr/share/fonts/truetype/dejavu')
if not (FONT_ROOT / 'DejaVuSans.ttf').is_file():
    raise SystemExit('Rendering requires DejaVu Sans fonts; install them before rebuilding this PDF.')
pdfmetrics.registerFont(TTFont('StatusSans', str(FONT_ROOT / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('StatusSans-Bold', str(FONT_ROOT / 'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFontFamily('StatusSans', normal='StatusSans', bold='StatusSans-Bold')
body = ParagraphStyle('body', fontName='StatusSans', fontSize=9.8, leading=13, spaceAfter=8)
title = ParagraphStyle('title', fontName='StatusSans-Bold', fontSize=18, leading=23, spaceAfter=10)

def markup(text):
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html.escape(text))

flow = []
for paragraph in (ROOT / 'docs/experiment2-status.md').read_text(encoding='utf-8').strip().split('\n\n'):
    heading = paragraph.startswith('# ')
    flow.append(Paragraph(markup(paragraph[2:] if heading else paragraph), title if heading else body))
output = ROOT / 'deliverables/COMP9500-Experiment2-Status.pdf'
SimpleDocTemplate(str(output), pagesize=(612,792), leftMargin=42, rightMargin=42,
                  topMargin=36, bottomMargin=36, title='COMP 9500 Research Status', author='Vibhor Malik').build(flow)
print(output)
