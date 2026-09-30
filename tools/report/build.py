#!/usr/bin/env python3
"""시장 톱니바퀴 아침보고서 A4 PDF 빌드.

사용: python3 tools/report/build.py 2026-09-30 [--preview]
  - tools/report/content_<날짜>.py 의 build(root) 가 페이지 HTML 목록을 돌려준다.
  - Chromium(headless)으로 PDF를 만들고, --preview 이면 페이지별 PNG도 만들어 육안 검수에 쓴다.
필요: Chromium (기본 /opt/pw-browsers/chromium-1194/chrome-linux/chrome 또는 CHROME_BIN),
      Noto Sans KR TTF 폴더 (NSK_FONT_DIR, 예: npm i @expo-google-fonts/noto-sans-kr 의 node_modules 경로).
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    date = args[0] if args else '2026-09-30'
    preview = '--preview' in sys.argv
    font_dir = os.environ.get('NSK_FONT_DIR', '')
    if not font_dir or not os.path.isdir(font_dir):
        raise SystemExit('NSK_FONT_DIR 에 Noto Sans KR 폴더(400Regular, 700Bold 포함)를 지정하라.')
    spec = importlib.util.spec_from_file_location('content', os.path.join(HERE, f'content_{date}.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pages = mod.build(ROOT)
    outdir = os.path.join(ROOT, 'docs', 'reports', date)
    os.makedirs(outdir, exist_ok=True)
    html_path = os.path.join(outdir, f'market_gear_{date}.html')
    pdf_path = os.path.join(outdir, f'market_gear_{date}_{mod.VER}.pdf')
    doc = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>%s %s</title><style>%s%s</style></head><body>%s</body></html>'
           % (mod.TITLE, date, lib.fontface(font_dir), lib.CSS, ''.join(pages)))
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    lib.to_pdf(html_path, pdf_path)
    try:
        import pymupdf
        d = pymupdf.open(pdf_path)
        print('pages', len(d))
        if preview:
            pv = os.path.join(os.environ.get('PREVIEW_DIR', outdir), 'preview')
            os.makedirs(pv, exist_ok=True)
            for i, p in enumerate(d, 1):
                p.get_pixmap(dpi=90).save(os.path.join(pv, f'p{i:02d}.png'))
            print('preview ->', pv)
    except ImportError:
        print('pymupdf 없음: 페이지 수 확인과 미리보기를 건너뜀')
    print('pdf ->', pdf_path)


if __name__ == '__main__':
    main()
