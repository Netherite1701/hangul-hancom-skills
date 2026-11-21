# -*- coding: utf-8 -*-
"""문서 글을 문단 단위로 내보낸다(읽기·찾을 글 고르기용).

사용: python dump.py <문서.hwpx> [--cells] [--styles] > out.txt
  번호  스타일  문단모양  글 (⏎ 줄바꿈, ⇥ 탭, <ctrl> 조판 부호)
  --cells  : 표 칸 안 문단도 '  [표 i r,c]'로 함께
  --styles : 스타일·글자 모양·문단 모양 목록을 먼저
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from hwpx_lib import Hwpx, q, qh, show_text, utf8_stdout

utf8_stdout()
doc = Hwpx(sys.argv[1]); cells = '--cells' in sys.argv
sty = {s.get('id'): s.get('name') for s in doc.head.iter(qh('style'))}
if '--styles' in sys.argv:
    fonts = doc.font_faces()
    for s in doc.head.iter(qh('style')):
        c = doc.char_pr(s.get('charPrIDRef')); p = doc.para_pr(s.get('paraPrIDRef'))
        al = p.find('.//' + qh('align')); ls = p.find('.//' + qh('lineSpacing'))
        print('style %3s %-12s char %s %.1fpt %s | para %s %s %s%%' % (
            s.get('id'), s.get('name'), c.get('id'), int(c.get('height')) / 100, fonts.get(c.find(qh('fontRef')).get('hangul')),
            p.get('id'), al.get('horizontal') if al is not None else '', ls.get('value') if ls is not None else ''))
    print('-' * 60)
k = 0
for i, p in enumerate(doc.top_paragraphs()):
    tbls = [t for t in p.iter(q('tbl')) if not any(a.tag == q('tbl') for a in t.iterancestors())]
    tag = ' <표 %d×%d>' % (int(tbls[0].get('rowCnt')), int(tbls[0].get('colCnt'))) if tbls else ''
    print('%4d %-10s pp%-3s%s %s' % (i, sty.get(p.get('styleIDRef'), p.get('styleIDRef')), p.get('paraPrIDRef'),
                                     ' [쪽나눔]' if p.get('pageBreak') == '1' else '', show_text(p) + tag))
    if cells:
        for tb in tbls:
            k += 1
            for r, tr in enumerate(tb.findall(q('tr'))):
                for c, tc in enumerate(tr.findall(q('tc'))):
                    txt = ' / '.join(show_text(x) for x in tc.findall('.//' + q('p')))
                    if txt.strip():
                        print('       [표 %d %d,%d] %s' % (k, r, c, txt))
