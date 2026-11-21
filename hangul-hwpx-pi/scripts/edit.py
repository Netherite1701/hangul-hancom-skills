# -*- coding: utf-8 -*-
"""JSON에 적은 수정을 차례로 적용한다. 원본은 두고 새 파일로 쓴다.

사용: python edit.py <원본.hwpx> <출력.hwpx> <수정.json>

수정.json은 배열. 각 항목의 "op"(없으면 replace):
  {"op":"replace", "find":"…", "replace":"…", "why":"…"}
      본문·표 칸·각주 전체에서 find가 정확히 한 번 나와야 한다. 짧지만 하나뿐인 글로 잡는다.
  {"op":"split_line", "line":"…코드 한 줄 전체…", "lines":["…","…"]}
      글이 정확히 line인 문단(코드 상자의 한 줄 등)을 여러 문단으로 나눈다. 같은 줄이 여러 상자에 있으면 모두.
  {"op":"keep_with_next", "para":"문단 첫 글", "nth":-1, "value":true}
      문단 모양을 복제해 '다음 문단과 함께'를 켠다(제목·설명을 다음 표와 같은 쪽에 두기). nth: 같은 글이 여럿일 때(-1 마지막).
  {"op":"page_break_before", "para":"문단 첫 글", "nth":-1, "value":true}
      '문단 앞에서 항상 쪽 나눔'. 되도록 keep_with_next를 먼저 쓴다(내용이 바뀌어도 알맞게 따라간다).
  {"op":"style", "name":"코드", "font":"돋움체", "size":9.5, "align":"LEFT", "line_spacing":160, "monospace":true}
      스타일이 가리키는 글자·문단 모양을 바꾼다. 그 모양을 스타일 밖(다른 문단)에서 같이 쓰면 멈춘다("force":true로 무시).
  {"op":"table_page_break", "value":"TABLE"}
      여러 쪽에 걸칠 수 있는 표의 쪽 나눔: TABLE(셀 단위, 행이 통째로 넘어감) / CELL(셀 안에서 나눔) / NONE.
  {"op":"note_to_footnote", "para":"주: 자료는", "anchor":"[표 1] ", "strip":"주:"}
      '주:' 같은 설명 문단을 anchor 문단(보통 그 표의 캡션) 끝의 한글 각주로 옮기고 원래 문단을 지운다.
      문서의 첫 각주를 본보기로 복제하므로 각주가 하나는 있어야 한다. 끝나면 각주 번호를 다시 매긴다.
      주 문단이 붙어 있던 캡션의 문단 모양(아래 간격)이 다른 캡션과 다르면 따로 맞춘다(para_shape op).
  {"op":"para_shape", "para":"[표 1] ", "like":"[표 3] "}
      문단 모양을 다른 문단과 같게 한다(복제하지 않고 같은 id를 가리킨다).
  {"op":"renumber_footnotes"}
      각주 번호를 문서 순서대로 다시 적는다(각주를 넣거나 지운 뒤).
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from hwpx_lib import (Hwpx, q, qh, clean, own_text, replace_text, split_line, set_char_pr, set_para_pr, add_footnote,
                      utf8_stdout)

utf8_stdout()
src, dst, spec = sys.argv[1], sys.argv[2], sys.argv[3]
doc = Hwpx(src)
ops = json.load(open(spec, encoding='utf-8'))
assert isinstance(ops, list), '수정.json은 배열이어야 한다'
for n, op in enumerate(ops, 1):
    kind = op.get('op', 'replace'); name = '%d(%s)' % (n, kind)
    if kind == 'replace':
        where = replace_text(doc, op['find'], op['replace'], name)
        print('%s [%s] %r → %r' % (name, where, op['find'][:40], op['replace'][:40]))
    elif kind == 'split_line':
        k = split_line(doc, op['line'], op['lines'], name)
        print('%s %d곳: %r → %d줄' % (name, k, op['line'].strip()[:40], len(op['lines'])))
    elif kind in ('keep_with_next', 'page_break_before'):
        p = doc.find(op['para'], nth=op.get('nth'))
        args = {kind: op.get('value', True)}
        nid = doc.clone_para_pr(p.get('paraPrIDRef'), **args)
        print('%s %r: 문단 모양 %s → %s' % (name, own_text(p)[:30], p.get('paraPrIDRef'), nid))
        p.set('paraPrIDRef', nid); clean(p)
    elif kind == 'style':
        s = doc.style(op['name']); cid, pid = s.get('charPrIDRef'), s.get('paraPrIDRef')
        for k_, i_ in (('char', cid), ('para', pid)):
            body, cell, styles = doc.users_of(k_, i_)
            others = [x for x in styles if x != op['name']]
            if others and not op.get('force'):
                raise SystemExit('ERROR %s: %s 모양 %s를 다른 스타일 %s도 쓴다(force로 무시)' % (name, k_, i_, others))
            print('%s %s 모양 %s: 본문 %d, 표 칸 %d곳에서 쓰임' % (name, k_, i_, body, cell))
        fid = doc.add_font(op['font'], monospace=op.get('monospace', False)) if op.get('font') else None
        set_char_pr(doc.char_pr(cid), height=round(op['size'] * 100) if op.get('size') else None, font_id=fid)
        set_para_pr(doc.para_pr(pid), align=op.get('align'), line_spacing=op.get('line_spacing'))
        for sec in doc.sections:
            for p in sec.iter(q('p')):
                if p.get('styleIDRef') == s.get('id'):
                    clean(p)
        print('%s 스타일 %r: 글꼴 %s 크기 %s 정렬 %s 줄 간격 %s' % (name, op['name'], op.get('font'), op.get('size'), op.get('align'), op.get('line_spacing')))
    elif kind == 'table_page_break':
        k = 0
        for sec in doc.sections:
            for tb in sec.iter(q('tbl')):
                if tb.get('pageBreak') != op['value']:
                    tb.set('pageBreak', op['value']); clean(doc.top_of(tb)); k += 1
        print('%s 표 %d개 → %s' % (name, k, op['value']))
    elif kind == 'note_to_footnote':
        note = doc.find(op['para'], nth=op.get('nth')); anchor = doc.find(op['anchor'], nth=op.get('anchor_nth'))
        body = own_text(note).strip()
        pre = op.get('strip', '')
        if pre and body.startswith(pre):
            body = body[len(pre):].strip()
        add_footnote(doc, anchor, body)
        note.getparent().remove(note)
        total, changed = doc.renumber_footnotes()
        print('%s %r → %r 끝 각주(%d자), 각주 %d개로 다시 매김' % (name, op['para'][:20], op['anchor'][:20], len(body), total))
    elif kind == 'para_shape':
        p = doc.find(op['para'], nth=op.get('nth')); like = doc.find(op['like'], nth=op.get('like_nth'))
        print('%s %r: 문단 모양 %s → %s(%r와 같게)' % (name, op['para'][:20], p.get('paraPrIDRef'), like.get('paraPrIDRef'), op['like'][:20]))
        p.set('paraPrIDRef', like.get('paraPrIDRef')); clean(p)
    elif kind == 'renumber_footnotes':
        total, changed = doc.renumber_footnotes()
        print('%s 각주 %d개, 바뀐 번호 %s' % (name, total, changed or '없음'))
    else:
        raise SystemExit('ERROR %s: 모르는 op %r' % (name, kind))
doc.save(dst)
print('written', dst)
