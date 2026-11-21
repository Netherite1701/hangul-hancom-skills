# -*- coding: utf-8 -*-
"""표 하나의 열 너비를 글 폭에 맞게 다시 나누고, 칸 안의 줄을 낱말 단위로 직접 나눈다(낱말 중간 끊김 방지).

사용: python fit_table.py <원본.hwpx> <출력.hwpx> --caption "[표 2] " [--width 41952] [--safe 1.04] [--rejoin] [--keep-lines]

- 칸 안의 문단·줄바꿈은 그대로 줄 단위로 두고(글쓴이가 나눈 줄), 칸보다 긴 줄만 다시 나눈다.
  표 전체 줄 수가 가장 적은 열 너비를 고른다(열이 4개 이하면 200 단위로 모든 조합, 5개 이상이면 줄 수를 가장 많이 줄이는 열부터 넓힌다).
- --rejoin: 칸 안의 줄을 모두 한 줄로 이은 뒤 처음부터 다시 나눈다(손으로 나눈 줄이 엉망일 때).
- 줄은 빈칸 뒤 또는 가운뎃점(·) 뒤에서 나누고 <hp:lineBreak/>로 적는다. 칸에는 문단 하나만 남긴다(첫 문단 모양·글자 모양).
- 글이 있는 행의 높이는 칸 위아래 여백 합(최소값)으로 낮춘다. 한컴이 열 때 글에 맞춰 늘린다(옛 높이가 남으면 칸이 비어 보인다).
  빈 행(서식의 쓰는 칸)은 높이를 그대로 둔다.
- --keep-lines: 줄 구성은 그대로 두고, 각 줄이 들어가는 최소 너비를 지키며 표 너비만 --width로 맞춘다.
- --width 기본값은 지금 표 너비. 본문 폭에 꽉 차는 표는 바깥 여백 때문에 (본문 폭 − 좌우 바깥 여백)으로 잡아야
  한컴이 마지막 열을 줄이지 않는다(예: 본문 42520, 바깥 여백 283×2 → 41952).
- --safe: 글 폭 계산에 곱하는 여유(1.04~1.06). 렌더해 보고 낱말이 끊기면 올리고, 줄이 너무 일찍 나뉘면 내린다.
"""
import argparse, itertools, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from hwpx_lib import Hwpx, Meter, q, qh, clean, para_margins, utf8_stdout
from lxml import etree

utf8_stdout()
ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--caption', required=True)
ap.add_argument('--width', type=int); ap.add_argument('--safe', type=float, default=1.04)
ap.add_argument('--keep-lines', action='store_true'); ap.add_argument('--rejoin', action='store_true')
a = ap.parse_args()

doc = Hwpx(a.src)
para, tbl = doc.table_by_caption(a.caption)
trs = tbl.findall(q('tr')); n = int(tbl.get('colCnt'))
assert all(len(tr.findall(q('tc'))) == n for tr in trs), '셀 합치기가 있는 표는 아직 다루지 않는다'
TOTAL = a.width or int(tbl.find(q('sz')).get('width'))
fonts = doc.font_faces(); meters = {}


def meter_of(tc):
    r = tc.find('.//' + q('run')); cid = r.get('charPrIDRef')
    if cid not in meters:
        c = doc.char_pr(cid); fr = c.find(qh('fontRef')); ra = c.find(qh('ratio'))
        meters[cid] = Meter(fonts[fr.get('hangul')], int(c.get('height')) / 100, int(ra.get('hangul')) if ra is not None else 100)
    return meters[cid]


def pad_of(tc):
    m = tc.find(q('cellMargin')); p = tc.find('.//' + q('p'))
    pm = para_margins(doc.para_pr(p.get('paraPrIDRef')))
    return int(m.get('left')) + int(m.get('right')) + pm.get('left', 0) + pm.get('right', 0) + 20


def pieces(text):
    out = []
    for w in text.split(' '):
        parts = re.findall(r'[^·]+·?|·', w)
        out += [(x, k == 0) for k, x in enumerate(parts)]
    return out


def wrap_unit(text, width, meter, pad):
    room = (width - pad) / a.safe; lines, cur = [], ''
    for tok, sp in pieces(text):
        cand = (cur + (' ' if sp else '') + tok) if cur else tok
        if cur and meter.width(cand) > room:
            lines.append(cur); cur = tok
        else:
            cur = cand
    return lines + [cur]


def wrap(units, width, meter, pad):
    """units: 칸의 줄 목록(각 줄은 강제 줄바꿈). 긴 줄만 다시 나눈다. 빈 칸은 빈 줄 하나."""
    out = []
    for u in units or ['']:
        out += wrap_unit(u, width, meter, pad)
    return out


def cell_lines(tc):
    out = []
    for p in tc.iter(q('p')):
        cur = ''
        for t in p.iter(q('t')):
            cur += t.text or ''
            for c in t:
                if c.tag == q('lineBreak'):
                    out.append(cur); cur = ''
                cur += c.tail or ''
        out.append(cur)
    return [x.strip() for x in out if x.strip()]


cells = [[tc for tc in tr.findall(q('tc'))] for tr in trs]
old = [int(tc.find(q('cellSz')).get('width')) for tc in cells[0]]

if a.keep_lines:
    need = [max((meter_of(tc).width(l) * a.safe + pad_of(tc) for row in cells for tc in [row[c]] for l in cell_lines(tc)), default=0)
            for c in range(n)]
    left = TOTAL - sum(need); assert left > 0, ('표 너비가 모자란다', round(sum(need)), TOTAL)
    slack = [max(o - x, 1) for o, x in zip(old, need)]
    ws = [x + left * s / sum(slack) for x, s in zip(need, slack)]
else:
    texts = []                                   # texts[행][열] = 줄 목록
    for row in cells:
        r = []
        for tc in row:
            units = cell_lines(tc)
            if a.rejoin and units:
                s = ''
                for x in units:
                    s += x if (not s or s.endswith('·')) else ' ' + x
                units = [re.sub(r'\s+', ' ', s)]
            r.append(units)
        texts.append(r)
    M = [meter_of(cells[0][c]) for c in range(n)]                    # 열마다 첫 행 글자 모양(머리 행)
    MB = [meter_of(cells[min(1, len(cells) - 1)][c]) for c in range(n)]
    P = [max(pad_of(row[c]) for row in cells) for c in range(n)]
    mtr = lambda ri, c: M[c] if ri == 0 else MB[c]
    base = [int(max([mtr(ri, c).width(w) for ri, r in enumerate(texts) for u in r[c] for w, _ in pieces(u)] or [0]) * a.safe + P[c]) + 1
            for c in range(n)]
    left = TOTAL - sum(base); assert left > 0, ('가장 긴 낱말들도 들어가지 않는다', sum(base), TOTAL)
    lines_at = lambda c, w: tuple(len(wrap(r[c], w, mtr(ri, c), P[c])) for ri, r in enumerate(texts))
    if n <= 4:
        cand = [list(range(base[c], base[c] + left + 1, 200)) for c in range(n)]
        tab = [{w: lines_at(c, w) for w in cand[c]} for c in range(n)]
        best = None
        for combo in itertools.product(*cand[:-1]):
            rest = TOTAL - sum(combo)
            if rest < base[-1]:
                continue
            last = base[-1] + (rest - base[-1]) // 200 * 200
            cols = [tab[c][w] for c, w in enumerate(combo)] + [tab[-1][last]]
            ls = [max(x) for x in zip(*cols)]
            key = (sum(ls), max(ls), sum(map(sum, cols)))
            if best is None or key < best[0]:
                best = (key, list(combo) + [rest])
        ws = best[1]
    else:
        ws = base[:]

        def height(v):
            # 표 높이(행마다 가장 긴 칸의 줄 수 합)를 먼저, 같으면 모든 칸의 줄 수 합(덜 끊긴 쪽)을 줄인다
            ls = [[len(wrap(r[c], v[c], mtr(ri, c), P[c])) for c in range(n)] for ri, r in enumerate(texts)]
            return sum(max(x) for x in ls) * 1000 + sum(map(sum, ls))
        while left > 0:
            cur = height(ws); pick = None
            for c in range(n):
                d = 100
                while d <= left:
                    v = ws[:]; v[c] += d; gain = cur - height(v)
                    if gain > 0:
                        if pick is None or d / gain < pick[0]:
                            pick = (d / gain, c, d)
                        break
                    d += 100
            if pick is None:
                break
            ws[pick[1]] += pick[2]; left -= pick[2]
        tot = sum(ws); ws = [x + left * x / tot for x in ws]
out = [int(x) for x in ws]; out[-1] += TOTAL - sum(out)

maxl = 0
for ri, row in enumerate(cells):
    has_text = any(cell_lines(tc) for tc in row)
    for c, tc in enumerate(row):
        tc.find(q('cellSz')).set('width', str(out[c]))
        m = tc.find(q('cellMargin'))
        if has_text:
            tc.find(q('cellSz')).set('height', str(int(m.get('top')) + int(m.get('bottom'))))
        if a.keep_lines or not cell_lines(tc):
            continue
        sub = tc.find(q('subList')); ps = sub.findall(q('p'))
        for p in ps[1:]:
            sub.remove(p)
        p = ps[0]; runs = p.findall(q('run'))
        for r in runs[1:]:
            p.remove(r)
        r = runs[0]
        for ch in list(r):
            r.remove(ch)
        ls = wrap(texts[ri][c], out[c], mtr(ri, c), P[c]); maxl = max(maxl, len(ls))
        t = etree.SubElement(r, q('t')); t.text = ls[0]
        for x in ls[1:]:
            lb = etree.SubElement(t, q('lineBreak')); lb.tail = x
tbl.find(q('sz')).set('width', str(TOTAL))
clean(para)
doc.save(a.dst)
print('%s 열 너비 %s → %s%s' % (a.caption.strip(), old, out, '' if a.keep_lines else ', 가장 긴 칸 %d줄' % maxl))
print('written', a.dst)
