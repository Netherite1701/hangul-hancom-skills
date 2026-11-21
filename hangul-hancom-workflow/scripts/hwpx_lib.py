# -*- coding: utf-8 -*-
"""HWPX(한글) 문서를 lxml로 고칠 때 쓰는 공통 함수.

다른 스크립트는 `sys.path.insert(0, <이 폴더>)` 뒤 `from hwpx_lib import *` 로 쓴다.

핵심 약속
- 파일을 열면 zip 항목 순서와 압축 방식을 그대로 기억했다가 같은 순서로 다시 쓴다(한컴이 순서를 따진다).
- 고친 문단에서는 hp:linesegarray(줄 배치 캐시)를 지운다. 남겨 두면 한컴이 옛 배치를 그대로 쓴다.
- 찾기는 항상 '정확히 하나'를 확인한다(assert). 여러 개면 멈춘다.
- 단위: HWPUNIT, 1pt = 100, 1mm ≈ 283.46.
"""
import copy, glob, json, os, re, sys, zipfile
from lxml import etree

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
HH = 'http://www.hancom.co.kr/hwpml/2011/head'
HS = 'http://www.hancom.co.kr/hwpml/2011/section'
q = lambda t: '{%s}%s' % (HP, t)
qh = lambda t: '{%s}%s' % (HH, t)
LANGS = ('hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user')
# 캡션 꼴: '[표 3] …', '<표 3> …', '표 3. …', '[별첨 표 2] …', '[그림 1] …', '[코드 1] …'.
# 번호 뒤에 빈칸이 와야 한다('[표 3]은 …' 같은 본문 문장은 캡션이 아니다).
CAPTION = re.compile(r'^[\[<]?\s*((?:별첨\s*)?(?:표|그림|코드|수식|사진|도표))\s*(\d+)\s*[\]>.:]\s')


def utf8_stdout():
    try:
        sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


# ---------------------------------------------------------------- 글 읽기
def own_text(p):
    """문단 p 자신의 글(표 칸·각주 같은 안쪽 문단의 글은 빼고, 줄바꿈·탭 뒤 글은 넣는다)."""
    out = []
    for r in p.findall(q('run')):
        for t in r.findall(q('t')):
            out.append(t.text or '')
            for c in t:
                out.append(c.tail or '')
    return ''.join(out)


def show_text(p):
    """사람이 읽기 좋게: 줄바꿈 ⏎, 탭 ⇥, 그 밖의 요소는 <이름>."""
    out = []
    for r in p.findall(q('run')):
        for t in r.findall(q('t')):
            out.append(t.text or '')
            for c in t:
                name = etree.QName(c).localname
                out.append({'lineBreak': '⏎', 'tab': '⇥'}.get(name, '<%s>' % name) + (c.tail or ''))
    return ''.join(out)


def clean(e):
    """e 아래의 줄 배치 캐시(linesegarray)를 모두 지운다."""
    for la in list(e.iter(q('linesegarray'))):
        la.getparent().remove(la)


def in_cell(e):
    return any(a.tag == q('tc') for a in e.iterancestors())


def in_footnote(e):
    return any(a.tag in (q('footNote'), q('endNote')) for a in e.iterancestors())


def norm(s):
    return re.sub(r'\s+', '', s or '')


# ---------------------------------------------------------------- 문서
class Hwpx:
    """hwpx 파일 하나. sections: 구역 XML 목록(section0, section1 …), head: header.xml."""

    def __init__(self, path):
        self.path = path
        z = zipfile.ZipFile(path)
        self.items = [(i, z.read(i.filename)) for i in z.infolist()]
        z.close()
        self.files = {i.filename: d for i, d in self.items}
        names = sorted((n for n in self.files if re.fullmatch(r'Contents/section\d+\.xml', n)),
                       key=lambda n: int(re.findall(r'\d+', n)[-1]))
        self.section_names = names
        self.sections = [etree.fromstring(self.files[n]) for n in names]
        self.head = etree.fromstring(self.files['Contents/header.xml'])
        self.log = []

    # 저장 ------------------------------------------------------------
    def save(self, path):
        for n, s in zip(self.section_names, self.sections):
            self.files[n] = etree.tostring(s, xml_declaration=True, encoding='UTF-8', standalone=True)
        self.files['Contents/header.xml'] = etree.tostring(self.head, xml_declaration=True, encoding='UTF-8', standalone=True)
        tmp = path + '.tmp'
        out = zipfile.ZipFile(tmp, 'w')
        for it, _ in self.items:
            out.writestr(it, self.files[it.filename], compress_type=it.compress_type)
        out.close()
        os.replace(tmp, path)

    # 문단 ------------------------------------------------------------
    def top_paragraphs(self):
        """구역 바로 아래 문단(본문 흐름). 표·글상자는 이 문단의 run 안에 들어 있다."""
        out = []
        for s in self.sections:
            out += s.findall(q('p'))
        return out

    def all_paragraphs(self):
        """표 칸·각주·글상자 안까지 모든 문단."""
        for s in self.sections:
            yield from s.iter(q('p'))

    def top_of(self, e):
        """e를 품은 본문 문단."""
        secs = set(self.sections)
        while e.getparent() not in secs:
            e = e.getparent()
        return e

    def find(self, prefix, where='top', nth=None, exact=False):
        """글이 prefix로 시작하는(exact면 같은) 문단. 하나가 아니면 멈춘다. nth로 여럿 중 하나(예: -1 = 마지막)."""
        pool = self.top_paragraphs() if where == 'top' else list(self.all_paragraphs())
        hits = [p for p in pool if (own_text(p).strip() == prefix if exact else own_text(p).strip().startswith(prefix))]
        if nth is None:
            assert len(hits) == 1, ('문단 찾기: %r가 %d개' % (prefix, len(hits)))
            return hits[0]
        assert hits, ('문단 찾기: %r 없음' % prefix)
        return hits[nth]

    # 표 ---------------------------------------------------------------
    def tables(self, with_side=False):
        """(본문 문단, 표, 캡션 글[, 'below'|'above'|'']) — 표 안의 표는 뺀다.
        캡션: 표 다음 첫 비지 않은 문단이 캡션 꼴(CAPTION)이면 그것, 아니면 표 앞 비지 않은 문단이 캡션 꼴이면 그것.
        둘 다 아니면 표 다음 첫 비지 않은 문단의 글(캡션 없는 표)."""
        tops = self.top_paragraphs(); out = []
        for i, p in enumerate(tops):
            for tb in p.iter(q('tbl')):
                if any(a.tag == q('tbl') for a in tb.iterancestors()):
                    continue
                after = before = ''
                for j in range(i + 1, min(i + 3, len(tops))):
                    s = own_text(tops[j]).strip()
                    if s:
                        after = s; break
                for j in range(i - 1, max(i - 3, -1), -1):
                    s = own_text(tops[j]).strip()
                    if s:
                        before = s; break
                if CAPTION.match(after):
                    cap, side = after, 'below'
                elif CAPTION.match(before):
                    cap, side = before, 'above'
                else:
                    cap, side = after, ''
                out.append((p, tb, cap, side) if with_side else (p, tb, cap))
        return out

    def table_by_caption(self, prefix):
        hits = [(p, tb) for p, tb, cap in self.tables() if cap.startswith(prefix)]
        assert len(hits) == 1, ('표 찾기: 캡션 %r가 %d개' % (prefix, len(hits)))
        return hits[0]

    # 머리(header.xml) -------------------------------------------------
    def _list(self, tag):
        return self.head.find('.//' + qh(tag))

    def styles(self):
        return {s.get('name'): s for s in self.head.iter(qh('style'))}

    def style(self, name):
        s = self.styles().get(name)
        assert s is not None, ('스타일 없음: %r (있는 것: %s)' % (name, ', '.join(self.styles())))
        return s

    def para_pr(self, pid):
        return next(e for e in self.head.iter(qh('paraPr')) if e.get('id') == str(pid))

    def char_pr(self, cid):
        return next(e for e in self.head.iter(qh('charPr')) if e.get('id') == str(cid))

    def _clone(self, list_tag, item_tag, src):
        lst = self._list(list_tag)
        new = copy.deepcopy(src)
        nid = str(max(int(e.get('id')) for e in lst.findall(qh(item_tag))) + 1)
        new.set('id', nid); lst.append(new)
        lst.set('itemCnt', str(len(lst.findall(qh(item_tag)))))
        return nid, new

    def clone_para_pr(self, pid, keep_with_next=None, keep_lines=None, page_break_before=None,
                      align=None, line_spacing=None, break_non_latin=None):
        """문단 모양을 복제해 일부만 바꾼다. 새 id를 돌려준다."""
        nid, new = self._clone('paraProperties', 'paraPr', self.para_pr(pid))
        set_para_pr(new, keep_with_next, keep_lines, page_break_before, align, line_spacing, break_non_latin)
        return nid

    def clone_char_pr(self, cid, height=None, font_id=None):
        nid, new = self._clone('charProperties', 'charPr', self.char_pr(cid))
        set_char_pr(new, height, font_id)
        return nid

    def font_faces(self, lang='HANGUL'):
        for ff in self.head.iter(qh('fontface')):
            if ff.get('lang') == lang:
                return {f.get('id'): f.get('face') for f in ff.findall(qh('font'))}
        return {}

    def all_font_faces(self):
        return sorted({f.get('face') for f in self.head.iter(qh('font'))})

    def add_font(self, face, monospace=False):
        """모든 언어의 글꼴 목록에 face를 넣고(이미 있으면 그대로) id를 돌려준다. 언어마다 id가 같아야 한다."""
        fid = None
        for ff in self.head.iter(qh('fontface')):
            fs = ff.findall(qh('font'))
            hit = [f for f in fs if f.get('face') == face]
            if hit:
                i = hit[0].get('id')
            else:
                new = copy.deepcopy(fs[0]); i = str(max(int(f.get('id')) for f in fs) + 1)
                new.set('id', i); new.set('face', face)
                for s in new.findall(qh('substFont')):
                    new.remove(s)
                ti = new.find(qh('typeInfo'))
                if ti is not None and monospace:
                    ti.set('proportion', '9')            # PANOSE 9 = 고정폭
                ff.append(new); ff.set('fontCnt', str(len(ff.findall(qh('font')))))
            assert fid in (None, i), ('언어마다 글꼴 id가 다르다', face, fid, i)
            fid = i
        return fid

    def users_of(self, kind, pid):
        """글자 모양(kind='char') 또는 문단 모양(kind='para') id를 쓰는 곳: (본문 run/p 수, 표 칸 안 수, 스타일 이름들)."""
        attr = 'charPrIDRef' if kind == 'char' else 'paraPrIDRef'
        tag = q('run') if kind == 'char' else q('p')
        body = cell = 0
        for s in self.sections:
            for e in s.iter(tag):
                if e.get(attr) == str(pid):
                    if in_cell(e):
                        cell += 1
                    else:
                        body += 1
        st = [s.get('name') for s in self.head.iter(qh('style')) if s.get(attr) == str(pid)]
        return body, cell, st

    # 각주 ---------------------------------------------------------------
    def renumber_footnotes(self):
        """각주 번호를 문서 순서대로 1…N으로 다시 적는다(footNote@number와 안쪽 autoNum@num). 바뀐 목록을 돌려준다."""
        changed = []
        fns = [f for s in self.sections for f in s.iter(q('footNote'))]
        for k, fn in enumerate(fns, 1):
            ans = [a for a in fn.iter(q('autoNum')) if a.get('numType') == 'FOOTNOTE']
            assert len(ans) == 1, ('각주 %d: autoNum %d개' % (k, len(ans)))
            if fn.get('number') != str(k):
                changed.append('%s→%d' % (fn.get('number'), k))
            fn.set('number', str(k)); ans[0].set('num', str(k))
        return len(fns), changed

    def next_inst_id(self):
        ids = [int(e.get('instId')) for s in self.sections for e in s.iter() if e.get('instId')]
        return (max(ids) if ids else 1000000000) + 1


def para_margins(e):
    """문단 모양 e의 실제 여백(HWPUNIT): intent(첫 줄), left, right, prev(위), next(아래).
    한글 2022 이후 파일은 hp:switch 안 hp:case에 실제 값과 hp:default에 두 배 값을 함께 둔다.
    한컴 2020이 저장한 파일은 switch 없이 두 배 값만 둔다. 두 경우 모두 실제 값으로 돌려준다."""
    HC = 'http://www.hancom.co.kr/hwpml/2011/core'
    case = e.find('.//' + q('case'))
    m = case.find(qh('margin')) if case is not None else None
    half = m is None
    if m is None:
        m = e.find('.//' + qh('margin'))
    if m is None:
        return {}
    out = {}
    for c in m:
        v = int(c.get('value'))
        out[etree.QName(c).localname] = v // 2 if half else v
    return out


def set_para_pr(e, keep_with_next=None, keep_lines=None, page_break_before=None, align=None, line_spacing=None,
                break_non_latin=None):
    b = lambda v: '1' if v else '0'
    for bs in e.iter(qh('breakSetting')):
        if keep_with_next is not None:
            bs.set('keepWithNext', b(keep_with_next))
        if keep_lines is not None:
            bs.set('keepLines', b(keep_lines))
        if page_break_before is not None:
            bs.set('pageBreakBefore', b(page_break_before))
        if break_non_latin is not None:
            bs.set('breakNonLatinWord', break_non_latin)        # 'KEEP_WORD'(어절) / 'BREAK_WORD'(글자)
    if align is not None:
        for al in e.iter(qh('align')):
            al.set('horizontal', align)                         # LEFT, RIGHT, CENTER, JUSTIFY, DISTRIBUTE
    if line_spacing is not None:
        for ls in e.iter(qh('lineSpacing')):
            assert ls.get('type') == 'PERCENT', ('줄 간격이 비율이 아님', dict(ls.attrib))
            ls.set('value', str(line_spacing))


def set_char_pr(e, height=None, font_id=None):
    if height is not None:
        e.set('height', str(int(height)))
    if font_id is not None:
        fr = e.find(qh('fontRef'))
        for k in list(fr.attrib):
            fr.set(k, str(font_id))


# ---------------------------------------------------------------- 문구 수정(JSON)
def _segments(p):
    out = []
    for r in p.findall(q('run')):
        for t in r.findall(q('t')):
            out.append((r, t, None))
            for k, _ in enumerate(t):
                out.append((r, t, k))
    return out


def _get(seg):
    r, t, k = seg
    return (t.text if k is None else t[k].tail) or ''


def _put(seg, s):
    r, t, k = seg
    if k is None:
        t.text = s
    else:
        t[k].tail = s


def _adjacent(a, b):
    ra, ta, ka = a; rb, tb, kb = b
    if kb is not None:
        return False
    if (ka is None and len(ta)) or (ka is not None and ka != len(ta) - 1):
        return False
    if ra is rb:
        return ta.getnext() is tb
    return ta.getnext() is None and ra.getnext() is rb and rb[0] is tb


def replace_text(doc, find, rep, name=''):
    """문서 전체(본문·표 칸·각주)에서 find가 정확히 한 번 나오는지 확인하고 rep로 바꾼다.
    찾은 글이 여러 글 조각에 걸치면, 사이에 다른 요소가 없고 글자 모양이 같을 때만 합친다."""
    hits = []
    for p in doc.all_paragraphs():
        segs = _segments(p); text = ''.join(_get(s) for s in segs)
        start = text.find(find)
        while start >= 0:
            hits.append((p, segs, start)); start = text.find(find, start + 1)
    if len(hits) != 1:
        raise SystemExit('ERROR %s: %r가 %d번 나온다(정확히 한 번이어야 함)' % (name, find, len(hits)))
    p, segs, start = hits[0]; end = start + len(find)
    pos, span = 0, []
    for s in segs:
        L = len(_get(s))
        if pos < end and pos + L > start or (L == 0 and start < pos < end):
            span.append((s, pos))
        pos += L
    if len(span) == 1:
        s, p0 = span[0]; v = _get(s); _put(s, v[:start - p0] + rep + v[end - p0:])
    else:
        for (a, _), (b, _) in zip(span, span[1:]):
            if not _adjacent(a, b):
                raise SystemExit('ERROR %s: 찾은 글이 줄바꿈·탭·조판 부호를 사이에 두고 나뉘어 있다: %r' % (name, find))
            if a[0].get('charPrIDRef') != b[0].get('charPrIDRef'):
                raise SystemExit('ERROR %s: 찾은 글이 글자 모양이 다른 run에 걸쳐 있다: %r' % (name, find))
        (s0, p0), (s1, p1) = span[0], span[-1]
        _put(s0, _get(s0)[:start - p0] + rep + _get(s1)[end - p1:])
        for s, _ in span[1:]:
            _put(s, '')
            r, t, k = s
            if k is None and not len(t):
                r.remove(t)
                if not len(r):
                    r.getparent().remove(r)
    clean(p)
    if in_cell(p):
        clean(doc.top_of(p))
    return 'cell' if in_cell(p) else ('footnote' if in_footnote(p) else 'body')


def split_line(doc, line, lines, name=''):
    """글이 정확히 line인 문단(주로 코드 상자의 한 줄)을 여러 문단으로 나눈다. 같은 줄이 여러 곳에 있으면 모두.
    문단에 run과 t가 하나씩만 있을 때만 한다."""
    n = 0
    for p in list(doc.all_paragraphs()):
        runs = p.findall(q('run')); ts = [t for r in runs for t in r.findall(q('t'))]
        if len(ts) != 1 or len(ts[0]) or (ts[0].text or '') != line:
            continue
        ts[0].text = lines[0]; clean(p); prev = p
        for part in lines[1:]:
            new = copy.deepcopy(p); new.findall('.//' + q('t'))[0].text = part
            prev.addnext(new); prev = new
        clean(doc.top_of(p)); n += 1
    if not n:
        raise SystemExit('ERROR %s: 글이 정확히 %r인 문단이 없다' % (name, line))
    return n


def add_footnote(doc, anchor_p, body):
    """문단 anchor_p의 끝에 한글 각주를 단다. 문서의 첫 각주를 본보기로 복제한다(각주 모양·스타일·번호 서식 그대로).
    각주 글은 ' ' + body(번호 뒤 빈칸). 번호는 doc.renumber_footnotes()로 다시 매긴다."""
    tpl = next((f for s in doc.sections for f in s.iter(q('footNote'))), None)
    assert tpl is not None, '본보기 각주가 없다: 한글에서 각주를 하나 넣어 둔 뒤 다시 한다'
    ctrl = copy.deepcopy(tpl.getparent()); fn = ctrl.find(q('footNote'))
    fn.set('instId', str(doc.next_inst_id()))
    sub = fn.find(q('subList')); ps = sub.findall(q('p'))
    for p in ps[1:]:
        sub.remove(p)
    p = ps[0]; runs = p.findall(q('run'))
    num_run = next(r for r in runs if r.find('.//' + q('autoNum')) is not None)
    for r in runs:
        if r is not num_run:
            p.remove(r)
    for t in num_run.findall(q('t')):
        num_run.remove(t)
    etree.SubElement(num_run, q('t')).text = ' ' + body
    clean(ctrl)
    runs = anchor_p.findall(q('run')); assert runs, '각주를 달 문단에 글이 없다'
    last = runs[-1]
    last.append(ctrl); etree.SubElement(last, q('t'))      # 한글이 쓰는 모양: …글</t><ctrl><footNote/></ctrl><t/>
    clean(anchor_p)
    return fn


# ---------------------------------------------------------------- 글자 폭
_FONT_INDEX = None


def hancom_font_dirs():
    """한컴오피스가 Windows에 등록하지 않고 자기만 쓰는 TrueType 글꼴 폴더(예: 한컴바탕). GDI 목록에는 없지만 한컴은 쓴다."""
    out = []
    for pf in (os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), os.environ.get('ProgramFiles', r'C:\Program Files')):
        out += [d for d in glob.glob(os.path.join(pf, 'Hnc', '*', '*', 'Shared', 'TTF', '*')) if os.path.isdir(d)]
    return sorted(set(os.path.normcase(d) for d in out))


def _font_index_fc():
    """리눅스(라즈베리 파이 등): fc-list가 아는 글꼴의 모든 가족 이름(한글 이름 포함) → (파일, ttc 번호)."""
    import subprocess
    out = subprocess.run(['fc-list', '--format', '%{file}|%{index}|%{family}|%{fullname}\n'],
                         capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    idx = {}
    for line in out.splitlines():
        parts = line.split('|')
        if len(parts) < 3 or not parts[0].lower().endswith(('.ttf', '.otf', '.ttc')):
            continue
        f, k = parts[0], int(parts[1] or 0) & 0xFFFF          # 위 16비트는 가변 글꼴의 인스턴스 번호
        for nm in ','.join(parts[2:]).split(','):
            nm = nm.strip()
            if nm and nm not in idx:
                idx[nm] = [f, k]
    return idx


def font_index():
    """설치된 글꼴의 이름(한글·영문 이름 모두) → (파일, ttc 번호). Windows: Windows·사용자·한컴 전용 폴더(캐시 사용).
    리눅스: fc-list(글꼴은 ~/.local/share/fonts 등에 두고 fc-cache -f)."""
    global _FONT_INDEX
    if _FONT_INDEX is not None:
        return _FONT_INDEX
    if os.name != 'nt':
        _FONT_INDEX = _font_index_fc()
        return _FONT_INDEX
    cache = os.path.join(os.environ.get('LOCALAPPDATA', '.'), 'hangul-hancom-workflow', 'fontindex.json')
    dirs = [os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'Fonts')] + hancom_font_dirs()
    files = sorted(f for d in dirs for f in glob.glob(os.path.join(d, '*')) if f.lower().endswith(('.ttf', '.otf', '.ttc')))
    stamp = [len(files), max((os.path.getmtime(f) for f in files), default=0)]
    try:
        data = json.load(open(cache, encoding='utf-8'))
        if data.get('stamp') == stamp:
            _FONT_INDEX = data['index']; return _FONT_INDEX
    except Exception:
        pass
    from fontTools.ttLib import TTFont, TTCollection
    idx = {}
    for f in files:
        try:
            fonts = TTCollection(f, lazy=True).fonts if f.lower().endswith('.ttc') else [TTFont(f, lazy=True)]
        except Exception:
            continue
        for k, tf in enumerate(fonts):
            try:
                for r in tf['name'].names:
                    if r.nameID in (1, 4, 16):
                        nm = r.toUnicode().strip()
                        if nm and nm not in idx:
                            idx[nm] = [f, k]
            except Exception:
                pass
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump({'stamp': stamp, 'index': idx}, open(cache, 'w', encoding='utf-8'), ensure_ascii=False)
    _FONT_INDEX = idx
    return idx


class Meter:
    """글자 폭을 HWPUNIT으로 잰다. 한컴 PDF와 맞춰 본 값: 한컴은 빈칸을 글꼴 파일 값(함초롬 0.3em)보다 넓은 0.5em로 놓는다.
    face: 한컴 글꼴 이름(예 '함초롬돋움'), size_pt: 글자 크기, ratio: 장평(%), space_em: 빈칸 폭."""

    def __init__(self, face, size_pt, ratio=100, space_em=0.5, font_file=None, index=0):
        from PIL import ImageFont
        if font_file is None:
            hit = font_index().get(face)
            assert hit, ('글꼴 파일을 못 찾음: %r (설치 여부 확인, 또는 font_file 지정)' % face)
            font_file, index = hit
        self.font = ImageFont.truetype(font_file, 1000, index=index)
        self.unit = size_pt * 100 * ratio / 100.0
        self.space_em = space_em

    def em(self, s):
        return sum(self.space_em if ch == ' ' else self.font.getlength(ch) / 1000.0 for ch in s)

    def width(self, s):
        return self.em(s) * self.unit


def josa(word, pair):
    """받침에 맞는 조사. pair 예: ('은','는'), ('이','가'), ('과','와'), ('으로','로'), ('을','를').
    숫자로 끝나면 숫자 읽기로 판단(0 영, 1 일, 3 삼, 6 육, 7 칠, 8 팔은 받침; '으로/로'는 ㄹ받침 1·7·8에 '로')."""
    last = word.strip()[-1]
    if last.isdigit():
        has = last in '013678'; rieul = last in '178'
    elif '가' <= last <= '힣':
        jong = (ord(last) - 0xAC00) % 28; has = jong != 0; rieul = jong == 8
    else:
        has = False; rieul = False
    if pair == ('으로', '로'):
        return '로' if (not has or rieul) else '으로'
    return pair[0] if has else pair[1]
