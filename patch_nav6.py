import io

path = "cygnus.html"
with io.open(path, "r", encoding="utf-8", newline="") as f:
    raw = f.read()

had_crlf = "\r\n" in raw
c = raw.replace("\r\n", "\n")


def do(old, new, label):
    n = c.count(old)
    assert n == 1, f"{label}: anchor count={n}"
    return c.replace(old, new)


# 1) topwrap 을 더 이상 sticky 로 안 만듦 — 그냥 일반 문서 흐름대로 스크롤되게(트리 내비게이션째로 같이 스크롤되어 사라짐)
old_css = ".topwrap{position:sticky;top:0;z-index:6;background:var(--card)}"
new_css = ".topwrap{background:var(--card)}"
c = do(old_css, new_css, "topwrap-css-sticky-removed")

# 2) scrollToId: topwrap 이 더 이상 고정 안 되므로, topwrap 높이만큼 빼주던 보정 계산을 없애고
#    목표 el 위쪽에 살짝 여백(8px)만 두고 이동하도록 단순화
old_js = ("  function scrollToId(id){\n"
          "    var el=document.getElementById(id); if(!el) return;\n"
          "    var tw=document.querySelector('.topwrap');\n"
          "    var off=(tw?tw.getBoundingClientRect().height:0)+8;\n"
          "    var top=window.pageYOffset+el.getBoundingClientRect().top-off;\n"
          "    window.scrollTo({top:Math.max(0,top),behavior:'smooth'});\n"
          "  }")
new_js = ("  function scrollToId(id){\n"
          "    var el=document.getElementById(id); if(!el) return;\n"
          "    var top=window.pageYOffset+el.getBoundingClientRect().top-8;\n"
          "    window.scrollTo({top:Math.max(0,top),behavior:'smooth'});\n"
          "  }")
c = do(old_js, new_js, "scrollToId-simplified")

if had_crlf:
    c = c.replace("\n", "\r\n")

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(c)

print("patched OK")
