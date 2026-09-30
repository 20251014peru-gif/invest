"""시장 톱니바퀴 아침보고서 — A4 PDF 제작 도구 (표준 라이브러리만 사용).

HTML/CSS/SVG를 만들고 Chromium(headless)으로 PDF를 뽑는다. 내용은 content_YYYY-MM-DD.py 에 둔다.
"""
import html
import subprocess
import os
import shutil

NAVY = '#0F2A4A'
NAVY2 = '#1F3F6B'
INK = '#1A1F2B'
MUTED = '#5B6577'
LINE = '#D6DCE6'
SOFT = '#F2F5FA'
RED = '#C0392B'      # 위험
ORANGE = '#D9730D'   # 경계
BLUE = '#1F6FB2'     # 확인
TEAL = '#12867A'     # 완화
GRAY = '#8A93A3'


def esc(s):
    return html.escape(str(s))


CSS = """.badge{white-space:nowrap}
.tight table{font-size:7.4pt}.tight td,.tight th{padding:1mm 1.4mm}.tight .small{font-size:6.6pt}

@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: 'NSK', 'Noto Sans KR', sans-serif; color: #1A1F2B; font-size: 8.6pt; line-height: 1.42; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { position: relative; width: 210mm; height: 297mm; overflow: hidden; background: #fff; page-break-after: always; }
.page:last-child { page-break-after: auto; }
.hdr { position: absolute; left: 0; right: 0; top: 0; height: 15mm; background: #0F2A4A; color: #fff; padding: 0 13mm; display: flex; align-items: center; justify-content: space-between; }
.hdr .t { font-weight: 700; font-size: 11pt; letter-spacing: -0.2pt; }
.hdr .d { font-size: 8pt; opacity: .9; }
.body { position: absolute; left: 13mm; right: 13mm; top: 20mm; bottom: 15mm; }
.ftr { position: absolute; left: 13mm; right: 13mm; bottom: 6mm; border-top: 0.5pt solid #D6DCE6; padding-top: 1.6mm; font-size: 7pt; color: #5B6577; display: flex; justify-content: space-between; }
h1 { font-size: 15pt; margin: 0 0 1mm; color: #0F2A4A; letter-spacing: -0.3pt; }
h2 { font-size: 10.6pt; margin: 3.2mm 0 1.6mm; color: #0F2A4A; padding-bottom: 0.8mm; border-bottom: 1.2pt solid #0F2A4A; letter-spacing: -0.2pt; }
h3 { font-size: 9.2pt; margin: 2.4mm 0 1mm; color: #1F3F6B; }
p { margin: 0 0 1.6mm; }
.sub { color: #5B6577; font-size: 8pt; margin-bottom: 2mm; }
.lead { background: #0F2A4A; color: #fff; padding: 3.2mm 4mm; border-radius: 1.6mm; font-size: 10.6pt; line-height: 1.5; margin-bottom: 2.4mm; }
.lead b { color: #FFD9A0; }
.lead .s { font-size: 8.2pt; margin-top: 1.4mm; opacity: .92; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 3mm; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2.4mm; }
.card { border: 0.7pt solid #D6DCE6; border-radius: 1.6mm; padding: 2.4mm 2.8mm; background: #fff; }
.card.soft { background: #F2F5FA; }
.card .k { font-size: 7.4pt; color: #5B6577; margin-bottom: 0.6mm; }
.card .h { font-size: 9pt; font-weight: 700; color: #0F2A4A; margin-bottom: 1mm; line-height: 1.32; }
.card .v { font-size: 8pt; margin-bottom: 0.8mm; }
.card .n { font-size: 7.4pt; color: #5B6577; border-top: 0.5pt dashed #D6DCE6; margin-top: 1.2mm; padding-top: 1mm; }
.bar-l { border-left: 2.2pt solid #0F2A4A; }
.badge { display: inline-block; font-size: 7pt; font-weight: 700; color: #fff; padding: 0.3mm 1.6mm; border-radius: 1mm; vertical-align: 0.3pt; }
.b-red { background: #C0392B; } .b-orange { background: #D9730D; } .b-blue { background: #1F6FB2; } .b-teal { background: #12867A; } .b-gray { background: #8A93A3; } .b-navy { background: #0F2A4A; }
.t-red { color: #C0392B; font-weight: 700; } .t-orange { color: #D9730D; font-weight: 700; } .t-blue { color: #1F6FB2; font-weight: 700; } .t-teal { color: #12867A; font-weight: 700; } .t-gray { color: #5B6577; }
table { border-collapse: collapse; width: 100%; font-size: 7.6pt; }
th { background: #0F2A4A; color: #fff; text-align: left; padding: 1.1mm 1.6mm; font-weight: 700; }
td { padding: 1.1mm 1.6mm; border-bottom: 0.5pt solid #D6DCE6; vertical-align: top; }
tr:nth-child(even) td { background: #F7F9FC; }
td.num, th.num { text-align: right; white-space: nowrap; }
.small { font-size: 7.2pt; color: #5B6577; }
.chain { display: flex; align-items: stretch; gap: 0; margin: 1.2mm 0 1.6mm; }
.node { flex: 1; border: 0.9pt solid #8A93A3; border-radius: 1.4mm; padding: 1.4mm 1.6mm; font-size: 7.3pt; line-height: 1.32; background: #fff; }
.node .a { font-weight: 700; color: #0F2A4A; }
.node .b { color: #5B6577; font-size: 6.9pt; }
.node.red { border-color: #C0392B; background: #FBEFED; } .node.orange { border-color: #D9730D; background: #FDF3E8; } .node.blue { border-color: #1F6FB2; background: #EDF4FB; } .node.teal { border-color: #12867A; background: #E9F5F3; } .node.gray { border-color: #8A93A3; background: #F4F5F8; border-style: dashed; }
.arw { width: 5mm; display: flex; align-items: center; justify-content: center; color: #5B6577; font-size: 10pt; flex: none; }
.arw.warn { color: #D9730D; font-weight: 700; }
.gauge { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1mm; margin: 1.4mm 0; }
.gauge div { padding: 1.4mm 1.4mm; border-radius: 1.2mm; font-size: 7.2pt; text-align: center; background: #E7EBF2; color: #5B6577; border: 0.7pt solid #D6DCE6; }
.gauge div.on { background: #D9730D; color: #fff; border-color: #D9730D; font-weight: 700; }
.gauge div.na { background: #F4F5F8; border-style: dashed; }
.life { display: grid; grid-template-columns: 34mm repeat(7, 1fr); font-size: 7pt; }
.life .c { padding: 1mm 0.4mm; border-bottom: 0.5pt solid #D6DCE6; text-align: center; min-height: 6mm; display: flex; align-items: center; justify-content: center; }
.life .c.n { justify-content: flex-start; text-align: left; padding-left: 1mm; font-weight: 700; color: #0F2A4A; }
.life .hd { background: #0F2A4A; color: #fff; font-weight: 700; }
.dot { width: 3.2mm; height: 3.2mm; border-radius: 50%; display: inline-block; }
.note { font-size: 7.2pt; color: #5B6577; }
.warnbox { border-left: 2.4pt solid #D9730D; background: #FDF3E8; padding: 1.6mm 2.4mm; font-size: 7.6pt; margin: 1.4mm 0; }
.okbox { border-left: 2.4pt solid #1F6FB2; background: #EDF4FB; padding: 1.6mm 2.4mm; font-size: 7.6pt; margin: 1.4mm 0; }
.redbox { border-left: 2.4pt solid #C0392B; background: #FBEFED; padding: 1.6mm 2.4mm; font-size: 7.6pt; margin: 1.4mm 0; }
ul { margin: 0 0 1.4mm 4mm; padding: 0; } li { margin: 0 0 0.6mm; }
.tag { display: inline-block; font-size: 6.8pt; border: 0.6pt solid currentColor; padding: 0 1mm; border-radius: 0.8mm; margin-right: 0.6mm; }
.gap { border: 0.8pt dashed #8A93A3; border-radius: 1.4mm; padding: 2.4mm; background: #F4F5F8; font-size: 7.4pt; color: #5B6577; }
.gap b { color: #1A1F2B; }
"""


def fontface(font_dir):
    ff = ''
    for w, folder, name in ((400, '400Regular', 'NotoSansKR_400Regular.ttf'), (500, '500Medium', 'NotoSansKR_500Medium.ttf'), (700, '700Bold', 'NotoSansKR_700Bold.ttf')):
        p = os.path.join(font_dir, folder, name)
        if os.path.exists(p):
            ff += "@font-face{font-family:'NSK';font-weight:%d;src:url('file://%s');}\n" % (w, p)
    return ff


def page(n, total, title, date_txt, ver, body, foot_note):
    return f"""<section class="page">
<div class="hdr"><div class="t">{esc(title)}</div><div class="d">{esc(date_txt)} · {esc(ver)}</div></div>
<div class="body">{body}</div>
<div class="ftr"><span>판 {esc(ver)} · {esc(foot_note)}</span><span>{n} / {total}</span></div>
</section>"""


def badge(text, color):
    return f'<span class="badge b-{color}">{esc(text)}</span>'


def sign_txt(v, unit='%', dec=2, word_up='상승', word_dn='하락'):
    if v is None:
        return '—'
    if abs(v) < 10 ** -(dec + 1):
        return '보합'
    s = '+' if v > 0 else '−'
    return f'{s}{abs(v):.{dec}f}{unit} {word_up if v > 0 else word_dn}'


# ---------------------------------------------------------------- charts
def line_chart(cats, series, title, w=330, h=188, hlines=(), ymin=None, ymax=None, fmt='{:.2f}', xtick_every=3, markers=None, note=None, lo_pad=0.08):
    """series: [{'name','color','vals','dash':bool,'hollow_last':bool,'width':float}] vals may contain None.
    hlines: [(value,label,color)]  markers: [(cat_index,text)] vertical dotted markers."""
    L, R, T, B = 40, 62, 26, 24
    pw, ph = w - L - R, h - T - B
    allv = [v for s in series for v in s['vals'] if v is not None] + [hl[0] for hl in hlines]
    lo = min(allv) if ymin is None else ymin
    hi = max(allv) if ymax is None else ymax
    pad = (hi - lo) * lo_pad or 1
    lo, hi = (lo - pad if ymin is None else lo), (hi + pad if ymax is None else hi)
    n = len(cats)

    def X(i):
        return L + (pw * i / (n - 1) if n > 1 else pw / 2)

    def Y(v):
        return T + ph - (v - lo) / (hi - lo) * ph

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{esc(title)}" font-family="NSK, sans-serif">']
    out.append(f'<text x="0" y="12" font-size="10.5" font-weight="700" fill="{NAVY}">{esc(title)}</text>')
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = Y(v)
        out.append(f'<line x1="{L}" x2="{L + pw}" y1="{y:.1f}" y2="{y:.1f}" stroke="#E3E8F0" stroke-width="0.6"/>')
        out.append(f'<text x="{L - 4}" y="{y + 2.6:.1f}" font-size="7.6" text-anchor="end" fill="{MUTED}">{fmt.format(v)}</text>')
    for i, c in enumerate(cats):
        if i % xtick_every == 0 or i == n - 1:
            out.append(f'<text x="{X(i):.1f}" y="{h - 8}" font-size="7.4" text-anchor="middle" fill="{MUTED}">{esc(c)}</text>')
    for (val, label, col) in hlines:
        y = Y(val)
        out.append(f'<line x1="{L}" x2="{L + pw}" y1="{y:.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="0.9" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{L + pw + 3}" y="{y + 2.6:.1f}" font-size="6.8" fill="{col}">{esc(label)}</text>')
    for (idx, txt) in (markers or []):
        out.append(f'<line x1="{X(idx):.1f}" x2="{X(idx):.1f}" y1="{T}" y2="{T + ph}" stroke="{GRAY}" stroke-width="0.7" stroke-dasharray="1.5 2"/>')
        out.append(f'<text x="{X(idx) + 2:.1f}" y="{T + 8}" font-size="6.6" fill="{MUTED}">{esc(txt)}</text>')
    for s in series:
        d = ''
        pen = False
        for i, v in enumerate(s['vals']):
            if v is None:
                pen = False
                continue
            d += f'{"L" if pen else "M"}{X(i):.1f} {Y(v):.1f} '
            pen = True
        dash = ' stroke-dasharray="4 3"' if s.get('dash') else ''
        out.append(f'<path d="{d}" fill="none" stroke="{s["color"]}" stroke-width="{s.get("width", 1.6)}"{dash}/>')
        last = max((i for i, v in enumerate(s['vals']) if v is not None), default=None)
        if last is not None:
            hv = s['vals'][last]
            fill = '#fff' if s.get('hollow_last') else s['color']
            out.append(f'<circle cx="{X(last):.1f}" cy="{Y(hv):.1f}" r="3" fill="{fill}" stroke="{s["color"]}" stroke-width="1.4"/>')
            out.append(f'<text x="{X(last) + 5:.1f}" y="{Y(hv) - 1:.1f}" font-size="7.8" font-weight="700" fill="{s["color"]}">{fmt.format(hv)}</text>')
            out.append(f'<text x="{X(last) + 5:.1f}" y="{Y(hv) + 8:.1f}" font-size="6.8" fill="{s["color"]}">{esc(s["name"])}</text>')
    out.append('</svg>')
    svg = ''.join(out)
    cap = f'<div class="note">{esc(note)}</div>' if note else ''
    return f'<div>{svg}{cap}</div>'


def index100(vals):
    base = next((v for v in vals if v is not None), None)
    return [None if v is None else v / base * 100 for v in vals]


# ---------------------------------------------------------------- render
CHROME = os.environ.get('CHROME_BIN', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')


def to_pdf(html_path, pdf_path):
    if not os.path.exists(CHROME):
        found = shutil.which('chromium') or shutil.which('google-chrome')
        if not found:
            raise SystemExit('Chromium 실행 파일을 찾지 못했다. CHROME_BIN 환경변수를 지정하라.')
        chrome = found
    else:
        chrome = CHROME
    subprocess.run([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer',
                    f'--print-to-pdf={pdf_path}', 'file://' + os.path.abspath(html_path)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)

