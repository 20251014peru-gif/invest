"""시세 등락률·Top10 엑셀 만들기. 사용: python3 build_xlsx.py [출력.xlsx] [--csv 시세.csv]
CSV 열: 종목명,일자(YYYY-MM-DD),종가,거래량 (주봉 기준). 없으면 가짜 샘플 데이터로 만든다."""
import sys, csv, random, datetime as dt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.chart import LineChart, BarChart, Reference

MAXD, MAXS = 20000, 500          # 데이터 최대 행, 종목 최대 수
PERIODS = [("1주 전", 2), ("4주 전", 5), ("8주 전", 9), ("12주 전", 13), ("52주 전", 53), ("104주 전", 105)]
HEAD = PatternFill("solid", fgColor="DDE6F0"); BOLD = Font(bold=True)

def load(argv):
    out = next((a for a in argv[1:] if a.endswith(".xlsx")), "시세_등락률_Top10.xlsx")
    if "--csv" in argv:
        rows = []
        with open(argv[argv.index("--csv") + 1], encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows.append((r["종목명"], dt.date.fromisoformat(r["일자"]), float(r["종가"]), float(r["거래량"])))
        return out, rows, False
    random.seed(7); rows = []
    end = dt.date(2026, 10, 23)
    for i in range(1, 31):
        p = random.uniform(5000, 200000)
        for w in range(110):
            d = end - dt.timedelta(weeks=109 - w)
            p *= 1 + random.gauss(0.002, 0.04)
            rows.append((f"샘플종목{i:02d}", d, round(p), random.randint(10**5, 10**7)))
    return out, rows, True

out, rows, sample = load(sys.argv)
names = list(dict.fromkeys(r[0] for r in rows))
assert len(names) <= MAXS and len(rows) <= MAXD - 1

wb = Workbook()
# 설정
ws = wb.active; ws.title = "설정"
ws["A1"] = "기간"; ws["B1"] = "순번(1=가장 최근 주)"
for c in ("A1", "B1"): ws[c].font = BOLD; ws[c].fill = HEAD
for i, (lab, n) in enumerate(PERIODS, 2): ws.cell(i, 1, lab); ws.cell(i, 2, n)
ws["A10"] = "주봉 기준입니다. 일봉이면 순번을 바꾸세요(예: 1주 전=6). 순번은 종목별 최신 일자부터 1,2,3 으로 매겨집니다."
if sample: ws["A12"] = "※ 현재 데이터는 가짜 샘플입니다. 실제 시세가 아닙니다."; ws["A12"].font = Font(bold=True, color="C00000")
ws.column_dimensions["A"].width = 14; ws.column_dimensions["B"].width = 22

# 데이터
wd = wb.create_sheet("데이터")
for j, h in enumerate(["종목명", "일자", "종가", "거래량", "순번"], 1):
    c = wd.cell(1, j, h); c.font = BOLD; c.fill = HEAD
for i, (n, d, p, v) in enumerate(rows, 2):
    wd.cell(i, 1, n); wd.cell(i, 2, d).number_format = "yyyy-mm-dd"; wd.cell(i, 3, p); wd.cell(i, 4, v)
    wd.cell(i, 5, f'=IF(A{i}="","",COUNTIFS($A$2:$A${MAXD},A{i},$B$2:$B${MAXD},">"&B{i})+1)')
wd["G1"] = "A~D열에 붙여 넣고, E열 수식은 아래로 복사하세요."
for col, w in zip("ABCDE", (16, 12, 12, 14, 8)): wd.column_dimensions[col].width = w
wd.freeze_panes = "A2"

# 계산
wc = wb.create_sheet("계산")
wc["A1"] = "종목명"; wc["B1"] = "현재가"
for k, (lab, _) in enumerate(PERIODS): wc.cell(1, 3 + k, lab + " 대비")
for k, (lab, _) in enumerate(PERIODS): wc.cell(1, 10 + k, "정렬키 " + lab)
for c in wc[1]: c.font = BOLD; c.fill = HEAD
R = f"데이터!$A$2:$A${MAXD}"; P = f"데이터!$C$2:$C${MAXD}"; I = f"데이터!$E$2:$E${MAXD}"
for i in range(2, MAXS + 2):
    if i - 2 < len(names): wc.cell(i, 1, names[i - 2])
    wc.cell(i, 2, f'=IF($A{i}="","",IF(COUNTIFS({R},$A{i},{I},1)=0,"",SUMIFS({P},{R},$A{i},{I},1)))')
    for k in range(len(PERIODS)):
        s = f"설정!$B${2 + k}"
        wc.cell(i, 3 + k, f'=IFERROR(IF(OR($B{i}="",COUNTIFS({R},$A{i},{I},{s})=0),"",$B{i}/SUMIFS({P},{R},$A{i},{I},{s})-1),"")').number_format = "0.0%"
        col = wc.cell(i, 3 + k).column_letter
        wc.cell(i, 10 + k, f'=IF({col}{i}="","",{col}{i}+ROW()*0.000000001)')
    wc.cell(i, 2).number_format = "#,##0"
wc["A1"].comment = None
wc.freeze_panes = "B2"; wc.column_dimensions["A"].width = 16
for k in range(10, 16): wc.column_dimensions[wc.cell(1, k).column_letter].hidden = True
wc.conditional_formatting.add(f"C2:H{MAXS+1}", ColorScaleRule(start_type="min", start_color="F8696B", mid_type="num", mid_value=0, mid_color="FFFFFF", end_type="max", end_color="63BE7B"))

# 순위
wr = wb.create_sheet("순위")
wr["A1"] = "기간별 상위·하위 Top 10 (등락률 = 현재가 ÷ 과거가 − 1, 동률은 목록 순서대로)"; wr["A1"].font = BOLD
def block(top, r0):
    wr.cell(r0, 1, "상위 Top 10" if top else "하위 Top 10").font = BOLD
    wr.cell(r0 + 1, 1, "순위")
    for k, (lab, _) in enumerate(PERIODS):
        wr.cell(r0 + 1, 2 + 2 * k, lab); wr.cell(r0 + 1, 3 + 2 * k, "등락률")
    for c in wr[r0 + 1]: c.font = BOLD; c.fill = HEAD
    fn = "LARGE" if top else "SMALL"
    for n in range(1, 11):
        r = r0 + 1 + n; wr.cell(r, 1, n)
        for k in range(len(PERIODS)):
            key = f"계산!${wc.cell(1, 10 + k).column_letter}$2:${wc.cell(1, 10 + k).column_letter}${MAXS+1}"
            m = f"MATCH({fn}({key},$A{r}),{key},0)"
            wr.cell(r, 2 + 2 * k, f'=IFERROR(INDEX(계산!$A$2:$A${MAXS+1},{m}),"")')
            wr.cell(r, 3 + 2 * k, f'=IFERROR(INDEX(계산!${wc.cell(1, 3 + k).column_letter}$2:${wc.cell(1, 3 + k).column_letter}${MAXS+1},{m}),"")').number_format = "0.0%"
block(True, 3); block(False, 17)
wr.column_dimensions["A"].width = 8
for k in range(12): wr.column_dimensions[wr.cell(1, 2 + k).column_letter].width = 14 if k % 2 == 0 else 10

# 차트
wh = wb.create_sheet("차트")
wh["A1"] = "종목 선택"; wh["B1"] = names[0]; wh["B1"].fill = PatternFill("solid", fgColor="FFF2CC")
wh["C1"] = "← B1에 종목명을 입력하세요(계산 시트 A열의 이름과 같게)."
for j, h in enumerate(["순번", "일자", "종가", "거래량"], 1):
    c = wh.cell(3, j, h); c.font = BOLD; c.fill = HEAD
NPT = 110
for n in range(NPT, 0, -1):               # 오래된 → 최근
    r = 3 + (NPT - n + 1)
    wh.cell(r, 1, n)
    for col, src in ((2, "B"), (3, "C"), (4, "D")):
        cell = wh.cell(r, col, f'=IF(COUNTIFS({R},$B$1,{I},$A{r})=0,"",SUMIFS(데이터!${src}$2:${src}${MAXD},{R},$B$1,{I},$A{r}))')
    wh.cell(r, 2).number_format = "yyyy-mm-dd"
bar = BarChart(); bar.add_data(Reference(wh, min_col=4, min_row=3, max_row=3 + NPT), titles_from_data=True)
bar.set_categories(Reference(wh, min_col=2, min_row=4, max_row=3 + NPT)); bar.y_axis.title = "거래량"
line = LineChart(); line.add_data(Reference(wh, min_col=3, min_row=3, max_row=3 + NPT), titles_from_data=True)
line.y_axis.axId = 200; line.y_axis.title = "종가"; line.y_axis.crosses = "max"
bar += line; bar.title = "종가(선)와 거래량(막대)"; bar.height, bar.width = 10, 24
bar.x_axis.delete = False; bar.y_axis.delete = False; line.y_axis.delete = False
wh.add_chart(bar, "F3")
wh.column_dimensions["B"].width = 12

wb.save(out); print("saved", out, "종목", len(names), "행", len(rows), "샘플" if sample else "실데이터")
