# -*- coding: utf-8 -*-
"""한컴이 만든 PDF로 최종 점검: 캡션 번호, 캡션과 표가 같은 쪽인지, 각주, 쪽 번호, 아래가 빈 쪽, 긴 표의 제목 행 반복·쪽 나눔.

사용: python check.py <문서.hwpx> <같은 문서의 doc.pdf> [--label "-\\s*(\\d+)\\s*-"] [--blank 0.70] [--compare 이전.pdf]
캡션 꼴은 hwpx_lib.CAPTION('[표 3] …', '<표 3> …', '표 3. …', '[별첨 표 2] …', '[그림 1] …', '[코드 1] …').
캡션이 표 아래에 있든 위에 있든 알아본다.
"""
import argparse, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from hwpx_lib import Hwpx, CAPTION, q, own_text, norm, utf8_stdout
import fitz

utf8_stdout()
ap = argparse.ArgumentParser()
ap.add_argument('hwpx'); ap.add_argument('pdf')
ap.add_argument('--label', default=r'-\s*(\d+)\s*-')
ap.add_argument('--blank', type=float, default=0.70)
ap.add_argument('--compare')
a = ap.parse_args()

doc = Hwpx(a.hwpx); pdf = fitz.open(a.pdf)
problems = []
has_obj = lambda p: p is not None and any(p.find('.//' + q(t)) is not None for t in ('tbl', 'pic', 'equation', 'rect', 'container'))

# 1) 캡션 번호 ------------------------------------------------------------
tops = doc.top_paragraphs(); seqs = {}
for i, p in enumerate(tops):
    m = CAPTION.match(own_text(p).strip() + ' ')
    if not m:
        continue
    near = [tops[j] for j in (i - 1, i + 1) if 0 <= j < len(tops)]
    if has_obj(p) or any(has_obj(x) for x in near):
        seqs.setdefault(re.sub(r'\s+', ' ', m.group(1)), []).append(int(m.group(2)))
for k, v in seqs.items():
    ok = v == list(range(1, len(v) + 1))
    print('캡션 %-6s %2d개 %s' % (k, len(v), '연속' if ok else '연속 아님 %s' % v))
    if not ok:
        problems.append('캡션 %s 번호' % k)

# 2) 각주 ---------------------------------------------------------------
fns = [f for s in doc.sections for f in s.iter(q('footNote'))]
nums = [f.get('number') for f in fns]
ok = nums == [str(i) for i in range(1, len(fns) + 1)]
print('각주 %d개 %s' % (len(fns), ('번호 1~%d 연속' % len(fns)) if ok else '번호 이상 %s' % nums))
if not ok:
    problems.append('각주 번호')

# 3) PDF: 쪽 번호, 빈 쪽 --------------------------------------------------
labels, fill = [], []
for pg in pdf:
    m = [re.fullmatch(a.label, l.strip()) for l in pg.get_text().splitlines()]
    m = [x.group(1) for x in m if x]
    labels.append(m[-1] if m else None)
    H = pg.rect.height
    ys = [b[3] for b in pg.get_text('blocks') if b[3] < H * 0.93] + [d['rect'].y1 for d in pg.get_drawings() if d['rect'].y1 < H * 0.93]
    for im in pg.get_images(full=True):
        try:
            ys.append(pg.get_image_bbox(im).y1)
        except Exception:
            pass
    fill.append(max(ys) / H if ys else 0)
nums = [int(x) for x in labels if x]
cont = nums == list(range(nums[0], nums[0] + len(nums))) if nums else None
print('PDF %d장 | 쪽 번호 %s~%s | 번호 없는 장 %s | 연속 %s' % (len(pdf), nums[0] if nums else '-', nums[-1] if nums else '-',
      [i + 1 for i, x in enumerate(labels) if x is None], cont))
if cont is False:
    problems.append('쪽 번호')
print('아래가 빈 장(채운 높이 %.0f%% 미만): %s' % (a.blank * 100, [(i + 1, labels[i], round(v, 2)) for i, v in enumerate(fill) if v < a.blank]))

# 4) 캡션과 표가 같은 쪽인가, 긴 표 ---------------------------------------------
texts = [norm(pg.get_text()) for pg in pdf]
cur = 0


def row_text(tr):
    for tc in tr.findall(q('tc')):
        s = norm(''.join(own_text(x) for x in tc.iter(q('p'))))
        if len(s) >= 2:
            return s
    return ''


for p, tb, cap, side in doc.tables(with_side=True):
    if not side:
        continue
    key = norm(cap)[:18]
    pi = next((i for i in range(cur, len(texts)) if key in texts[i]), None)
    if pi is None:
        print('  ? 캡션을 PDF에서 못 찾음: %s' % cap[:30]); continue
    cur = pi
    rows = tb.findall(q('tr'))
    near = row_text(rows[-1] if side == 'below' else rows[0])       # 캡션 쪽 끝 행
    if near and near[:12] not in texts[pi]:
        print('  ! 캡션과 표가 다른 쪽: %s (캡션 %d장, 캡션이 표 %s)' % (cap[:30], pi + 1, '아래' if side == 'below' else '위'))
        problems.append('캡션 분리: ' + cap[:20])
    if len(rows) > 12 and tb.get('repeatHeader') != '1':
        print('  · 긴 표인데 제목 행 반복이 꺼져 있음: %s (%d행)' % (cap[:30], len(rows)))
    if tb.get('pageBreak') == 'CELL' and len(rows) > 12:
        print("  · 긴 표의 쪽 나눔이 CELL(셀 안에서 나눔): 한 행이 두 쪽에 갈릴 수 있음 → edit.py table_page_break TABLE: %s" % cap[:30])

# 5) 비교 ---------------------------------------------------------------
if a.compare:
    old = fitz.open(a.compare)
    t = lambda d: [[x[:4] for x in pg.get_text('blocks')] for pg in d]
    A, B = t(old), t(pdf)
    print('비교: %d장 → %d장, 배치가 달라진 장 %s' % (len(old), len(pdf), [i + 1 for i in range(min(len(A), len(B))) if A[i] != B[i]]))
    print('비교: 전체 글자 %d → %d' % (len(norm(''.join(pg.get_text() for pg in old))), len(norm(''.join(pg.get_text() for pg in pdf)))))
print('문제: %s' % ('; '.join(problems) if problems else '없음'))
