"""Build the factual recovery/progress report from its Markdown source."""
from pathlib import Path
import re, html
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
ROOT=Path(__file__).resolve().parents[1]
fonts=Path('/usr/share/fonts/truetype/dejavu')
for name,file in [('ReportSans','DejaVuSans.ttf'),('ReportSans-Bold','DejaVuSans-Bold.ttf')]:pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
pdfmetrics.registerFontFamily('ReportSans',normal='ReportSans',bold='ReportSans-Bold')
styles={'body':ParagraphStyle('body',fontName='ReportSans',fontSize=10,leading=14,spaceAfter=7), 'h1':ParagraphStyle('h1',fontName='ReportSans-Bold',fontSize=20,leading=25,spaceAfter=16), 'h2':ParagraphStyle('h2',fontName='ReportSans-Bold',fontSize=13,leading=18,spaceBefore=14,spaceAfter=8,keepWithNext=True)}
flow=[]
for block in (ROOT/'docs/final-progress-report.md').read_text().strip().split('\n\n'):
 block=block.strip()
 style='h1' if block.startswith('# ') else 'h2' if block.startswith('## ') else 'body'
 text=re.sub(r'^#{1,2} ','',block)
 text=html.escape(text).replace('\n','<br/>')
 text=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',text)
 flow.append(Paragraph(text,styles[style]))
out=ROOT/'deliverables/COMP9500-Final-Progress-Report.pdf'
def footer(c,d):
 c.setFont('ReportSans',8);c.setFillColorRGB(.35,.4,.45);c.drawString(44,25,'COMP 9500 | Research completion and publication readiness');c.drawRightString(568,25,str(d.page))
SimpleDocTemplate(str(out),pagesize=(612,792),leftMargin=44,rightMargin=44,topMargin=40,bottomMargin=44,title='COMP 9500 Final Progress Report').build(flow,onFirstPage=footer,onLaterPages=footer)
print(out)
