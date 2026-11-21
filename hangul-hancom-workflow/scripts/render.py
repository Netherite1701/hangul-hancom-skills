# -*- coding: utf-8 -*-
"""숨은 한컴으로 hwpx를 열어 PDF·쪽 그림을 만든다. 화면·마우스·키보드를 쓰지 않는다.

사용: python render.py <문서.hwpx> <출력폴더> [--resave <한컴이_다시_저장한.hwpx>] [--dpi 110] [--sheets]

- 원본은 열지 않고 임시 사본을 연다(원본에 잠금·변경 없음).
- 새 Hwp.exe가 뜨지 않으면(사용자가 띄워 둔 한컴에 붙으면) 아무것도 하지 않고 멈춘다.
- 한컴 자동화 보안 창('…접근하려는 시도', '모두 허용')은 hwp_allow.ps1과 안쪽 클리커가 눌러 준다.
- --resave: 한컴이 직접 저장한 hwpx를 남긴다. 최종 파일은 반드시 이것으로 낸다(줄 배치 캐시·스타일을 한컴이 다시 씀).
- 결과: <출력폴더>/doc.pdf, p01.png …, (--sheets) sheet_01.png …(3쪽씩).
- 시작 전에 문서가 쓰는 글꼴이 이 PC에 설치되어 있는지 본다. 없으면 PDF에서 다른 글꼴로 바뀌므로 경고한다.
"""
import argparse, os, shutil, subprocess, sys, tempfile, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hwpx_lib import Hwpx, utf8_stdout

utf8_stdout()
ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('out')
ap.add_argument('--resave'); ap.add_argument('--dpi', type=int, default=110)
ap.add_argument('--sheets', action='store_true')
ap.add_argument('--no-font-check', action='store_true')
a = ap.parse_args()

import fitz, psutil, win32com.client

src, out = os.path.abspath(a.src), os.path.abspath(a.out)
os.makedirs(out, exist_ok=True)
for f in os.listdir(out):
    if f.endswith(('.png', '.pdf')):
        os.remove(os.path.join(out, f))

# 사용자 글꼴 다시 올리기 ----------------------------------------------------------
# 관리자 권한 없이 설치한 사용자 글꼴(%LOCALAPPDATA%\Microsoft\Windows\Fonts)은 다시 로그인하면 목록에서 빠져 있을 때가 있다.
# 이번 로그인 세션에만 다시 올린다(설정·레지스트리는 바꾸지 않는다). 새로 뜨는 한컴이 이 글꼴을 본다.
import ctypes, glob
_ufonts = glob.glob(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'Fonts', '*.[to]t[fc]'))
if _ufonts:
    for _f in _ufonts:
        ctypes.windll.gdi32.AddFontResourceW(_f)
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 2, 3000, ctypes.byref(ctypes.c_ulong()))

# 글꼴 확인 ---------------------------------------------------------------
if not a.no_font_check:
    import win32gui
    names = set()
    dc = win32gui.GetDC(0)
    win32gui.EnumFontFamilies(dc, None, lambda lf, tm, ft, d: names.add(lf.lfFaceName) or 1, None)
    win32gui.ReleaseDC(0, dc)
    missing = [f for f in Hwpx(src).all_font_faces() if f not in names]
    if missing:                                  # 한컴 전용 글꼴 폴더(Hnc\…\Shared\TTF)에 있는 것은 한컴이 쓸 수 있다
        from hwpx_lib import font_index, hancom_font_dirs
        own = set(hancom_font_dirs())
        missing = [f for f in missing if not (f in font_index() and os.path.normcase(os.path.dirname(font_index()[f][0])) in own)]
    if missing:
        print('WARNING 설치되지 않은(또는 이번 로그인에서 풀린) 글꼴: %s → PDF에서 다른 글꼴로 바뀐다. '
              'fonts.ps1 -Reload 또는 -Install 로 올린 뒤 다시 만든다.' % ', '.join(missing))

tmp = os.path.join(tempfile.gettempdir(), 'hwp_render_%s.hwpx' % uuid.uuid4().hex[:8])
shutil.copy(src, tmp)
pdf = os.path.join(out, 'doc.pdf')

CLICKER = r'''
import time, win32gui, win32process, win32con, psutil
end = time.time() + 120
while time.time() < end:
    pids = {p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() == 'hwp.exe'}
    def top(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] not in pids or not win32gui.IsWindowVisible(h):
            return True
        btns = []
        win32gui.EnumChildWindows(h, lambda c, a: a.append((c, win32gui.GetWindowText(c))) or True, btns)
        for want in ('모두 허용', '접근 허용', '허용'):
            for c, t in btns:
                if want in t.replace('&', ''):
                    win32gui.SendMessage(c, win32con.BM_CLICK, 0, 0)
                    return True
        return True
    try:
        win32gui.EnumWindows(top, None)
    except Exception:
        pass
    time.sleep(0.2)
'''
clicker = subprocess.Popen([sys.executable, '-c', CLICKER])
allow = subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                          os.path.join(HERE, 'hwp_allow.ps1'), '-Seconds', '180'], creationflags=subprocess.CREATE_NO_WINDOW)
hwp_pids = lambda: {p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() == 'hwp.exe'}
before = hwp_pids()
hwp = win32com.client.DispatchEx('HWPFrame.HwpObject')
time.sleep(1.5)
if not (hwp_pids() - before):
    clicker.kill(); allow.kill(); del hwp; os.remove(tmp)
    sys.exit('ABORT: 이미 떠 있던 Hwp.exe에 붙었다(새 프로세스 없음). 사용자의 한컴이므로 아무것도 열거나 닫지 않았다.')
try:
    try:
        hwp.XHwpWindows.Item(0).Visible = False
    except Exception:
        pass
    hwp.SetMessageBoxMode(0x00000001 | 0x00000010 | 0x00000100 | 0x00001000 | 0x00010000)   # 확인·예 등 기본 응답
    assert hwp.Open(tmp, 'HWPX', 'forceopen:true'), 'open failed'
    pages = hwp.PageCount
    if a.resave:
        resave = os.path.abspath(a.resave)
        if os.path.exists(resave):
            os.remove(resave)
        print('resave', hwp.SaveAs(resave, 'HWPX', ''), resave)
    hwp.SaveAs(pdf, 'PDF', '')
    hwp.Clear(1)
finally:
    hwp.Quit()
    clicker.kill(); allow.kill()
    try:
        os.remove(tmp)
    except OSError:
        pass

doc = fitz.open(pdf)
print('pages(hwp)', pages, 'pages(pdf)', doc.page_count)
imgs = []
for i, pg in enumerate(doc, 1):
    path = os.path.join(out, 'p%02d.png' % i)
    pg.get_pixmap(dpi=a.dpi).save(path); imgs.append(path)
if a.sheets:
    from PIL import Image
    for s in range(0, len(imgs), 3):
        ims = [Image.open(p) for p in imgs[s:s + 3]]
        w, h = ims[0].size
        sheet = Image.new('RGB', (w * 3 + 40, h), 'gray')
        for k, im in enumerate(ims):
            sheet.paste(im, (k * (w + 20), 0))
        sheet.save(os.path.join(out, 'sheet_%02d.png' % (s // 3 + 1)))
used = sorted({f[3].split('+', 1)[-1] for pg in doc for f in pg.get_fonts()})
print('PDF fonts:', ', '.join(used))
print('ok', out)
