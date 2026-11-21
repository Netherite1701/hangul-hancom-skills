# -*- coding: utf-8 -*-
"""목차 줄의 쪽 번호를 한컴 PDF에서 읽어 넣는다(또는 --check로 비교만).

사용: python toc_pages.py <문서.hwpx> <같은 문서의 doc.pdf> [--check] [--styles "차례 1,차례 2,차례 3"] [--label "-\\s*(\\d+)\\s*-"]

목차 줄의 모양(한글 '차례 만들기'가 만드는 모양과 같게 둔다):
  문단 스타일 '차례 n', 제목 글 → <hp:tab leader=".." type="1"/> → 쪽 번호(탭 뒤 글).
  탭은 오른쪽 자동 탭(문단 모양의 tabPr autoTabRight="1")이어야 다른 한글 판에서도 번호가 오른쪽 끝에 붙는다.
쪽 번호는 각 쪽 아래에 찍힌 쪽 번호 글자(--label 정규식, 기본 '- N -')를 읽는다. 표지·목차처럼 번호가 없는 쪽도 맞게 센다.
"""
import argparse, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from hwpx_lib import Hwpx, q, qh, clean, norm, utf8_stdout
import fitz

utf8_stdout()
ap = argparse.ArgumentParser()
ap.add_argument('hwpx'); ap.add_argument('pdf'); ap.add_argument('--check', action='store_true')
ap.add_argument('--styles', default='')
ap.add_argument('--label', default=r'-\s*(\d+)\s*-')
a = ap.parse_args()

doc = Hwpx(a.hwpx)
wanted = [s.strip() for s in a.styles.split(',') if s.strip()]
st = doc.styles()
if not wanted:
    wanted = [n for n in st if re.fullmatch(r'(차례|목차|TOC|toc)\s*\d', n)]
ids = {st[n].get('id') for n in wanted if n in st}
assert ids, ('목차 스타일을 못 찾음. --styles로 지정. 스타일 목록: %s' % ', '.join(st))
ent = []
for p in doc.top_paragraphs():
    if p.get('styleIDRef') in ids:
        tab = p.find('.//' + q('tab'))
        if tab is not None:
            t = tab.getparent(); ent.append((p, tab, (t.text or '').strip()))
assert len(ent) >= 2, '목차 줄(탭이 있는 차례 문단)이 없다'

pdf = fitz.open(a.pdf)
pages = [norm(pg.get_text()) for pg in pdf]
lines = [[norm(l) for l in pg.get_text().split('\n') if l.strip()] for pg in pdf]
label = []
for pg in pdf:
    m = [re.fullmatch(a.label, l.strip()) for l in pg.get_text().splitlines()]
    m = [x.group(1) for x in m if x]
    label.append(int(m[-1]) if m else None)
# 목차가 끝나는 쪽: 마지막 두 목차 제목이 함께 있는 앞쪽 쪽들 가운데 마지막
toc_pages = [i for i, t in enumerate(pages[:12]) if norm(ent[-1][2]) in t and norm(ent[-2][2]) in t]
assert toc_pages, '앞 12쪽에서 목차 쪽을 못 찾음'
cur = toc_pages[-1] + 1; found = []; bad = []
for p, tab, title in ent:
    key = norm(title); hit = None
    for i in range(cur, len(pages)):
        if key in pages[i] and any(l.startswith(key[:10]) for l in lines[i]):
            hit = i; break
    if hit is None:
        bad.append(title); found.append(None); continue
    cur = hit; found.append(label[hit])
assert not bad, ('본문에서 제목을 못 찾음', bad)
diff = [(t, (tab.tail or '').strip(), n) for (p, tab, t), n in zip(ent, found) if (tab.tail or '').strip() != str(n)]
print('entries', len(ent), '| toc sheets up to', toc_pages[-1] + 1, '| differing', len(diff))
for d in diff[:80]:
    print('  ', d)
if not a.check and diff:
    for (p, tab, t), n in zip(ent, found):
        tab.tail = str(n); clean(p)
    doc.save(a.hwpx); print('written')
print(' '.join(str(n) for n in found))
