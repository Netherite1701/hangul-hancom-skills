# -*- coding: utf-8 -*-
"""한 줄에 들어가지 않을 줄을 미리 찾는다(코드 상자의 긴 줄, 표 칸에서 손으로 나눈 줄).

사용: python overflow.py <문서.hwpx> [--style 코드] [--safe 0.98]
- 1×1 표(상자) 안 문단 가운데 스타일이 --style인 것: 칸 안쪽 너비(칸 너비 − 좌우 여백)와 글 폭을 비교.
- 모든 표 칸: 줄바꿈(⏎)으로 나눈 줄 하나하나가 칸 안쪽 너비(+ 문단 왼쪽 여백)보다 넓으면 알린다.
  한컴은 칸보다 긴 줄을 낱말 중간에서 끊는다. 칸 너비를 넓히거나 줄을 다시 나눠야 한다.
글 폭은 hwpx_lib.Meter(글꼴 파일 실측, 빈칸 0.5em)로 잰다. 경계에 가까운 줄은 한컴 렌더로 꼭 확인한다.
"""
import argparse, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from hwpx_lib import Hwpx, Meter, q, qh, own_text, para_margins, utf8_stdout

utf8_stdout()
ap = argparse.ArgumentParser(); ap.add_argument('hwpx'); ap.add_argument('--style', default='코드')
ap.add_argument('--safe', type=float, default=0.98)
a = ap.parse_args()
doc = Hwpx(a.hwpx)
fonts = doc.font_faces(); meters = {}


def meter(cid):
    if cid not in meters:
        c = doc.char_pr(cid); fr = c.find(qh('fontRef')); ra = c.find(qh('ratio'))
        meters[cid] = Meter(fonts[fr.get('hangul')], int(c.get('height')) / 100, int(ra.get('hangul')) if ra is not None else 100)
    return meters[cid]


def para_left(pid):
    return para_margins(doc.para_pr(pid)).get('left', 0)


style_id = doc.styles().get(a.style).get('id') if a.style in doc.styles() else None
n = 0
for p, tb, cap in doc.tables():
    for tr in tb.findall(q('tr')):
        for tc in tr.findall(q('tc')):
            m = tc.find(q('cellMargin')); w = int(tc.find(q('cellSz')).get('width'))
            inner = w - int(m.get('left')) - int(m.get('right'))
            for cp in tc.findall('.//' + q('p')):
                runs = cp.findall(q('run'))
                if not runs:
                    continue
                cid = runs[0].get('charPrIDRef')
                room = inner - para_left(cp.get('paraPrIDRef'))
                parts = []
                for r in runs:
                    for t in r.findall(q('t')):
                        parts.append(t.text or '')
                        for c in t:
                            parts.append('\n' + (c.tail or '') if c.tag == q('lineBreak') else (c.tail or ''))
                for line in ''.join(parts).split('\n'):
                    wd = meter(cid).width(line)
                    if wd > room * a.safe:
                        n += 1
                        kind = '코드' if cp.get('styleIDRef') == style_id else '표 칸'
                        print('%s | %s | %.0f > %.0f (%.0f%%) | %r' % (kind, cap[:16], wd, room, wd / room * 100, line))
print('넘칠 줄 %d개' % n)
