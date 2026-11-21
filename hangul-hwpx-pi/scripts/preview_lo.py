# -*- coding: utf-8 -*-
"""한컴이 없을 때의 대략 미리보기: LibreOffice + H2Orestart 확장으로 hwpx를 PDF로 바꾸고 쪽 그림을 만든다.

사용: python3 preview_lo.py <문서.hwpx> <출력폴더> [--dpi 90]
준비: sudo apt install libreoffice-writer-nogui libreoffice-h2orestart   (또는 LibreOffice 확장 관리자로 H2Orestart 설치)

주의 — 이것은 한컴 렌더가 아니다.
- 글꼴·줄 나눔·표 높이 계산이 한컴과 달라 쪽 수·쪽 나눔·낱말 끊김이 다르게 나온다. 내용 확인(글이 바뀌었는지, 표가 깨지지 않았는지)에만 쓴다.
- 캡션 분리·빈 쪽·목차 쪽 번호 판단과 최종 PDF는 반드시 한컴 렌더(remote_render.py)로 한다.
- H2Orestart는 ODT로만 저장한다. 이 도구는 원본 hwpx를 바꾸지 않는다.
"""
import argparse, glob, os, shutil, subprocess, sys, tempfile

ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('--dpi', type=int, default=90)
a = ap.parse_args()
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
soffice = shutil.which('soffice') or shutil.which('libreoffice')
if not soffice:
    sys.exit('LibreOffice가 없다: sudo apt install libreoffice-writer-nogui libreoffice-h2orestart')
os.makedirs(a.out, exist_ok=True)
for f in glob.glob(os.path.join(a.out, '*.png')) + glob.glob(os.path.join(a.out, 'doc.pdf')):
    os.remove(f)
tmp = tempfile.mkdtemp(prefix='hwpx_lo_')
src = os.path.join(tmp, 'src.hwpx'); shutil.copy(a.src, src)
profile = 'file://' + os.path.join(tempfile.gettempdir(), 'hwpx_lo_profile')       # 사용자의 LibreOffice 설정과 섞이지 않게
p = subprocess.run([soffice, '-env:UserInstallation=' + profile, '--headless', '--norestore', '--convert-to', 'pdf', '--outdir', tmp, src],
                   capture_output=True, text=True, timeout=600)
pdf = os.path.join(tmp, 'src.pdf')
if not os.path.exists(pdf):
    sys.exit('변환 실패(H2Orestart가 설치되어 있는지 확인):\n' + p.stdout + p.stderr)
shutil.move(pdf, os.path.join(a.out, 'doc.pdf')); shutil.rmtree(tmp, ignore_errors=True)
try:
    import fitz
    doc = fitz.open(os.path.join(a.out, 'doc.pdf'))
    for i, pg in enumerate(doc, 1):
        pg.get_pixmap(dpi=a.dpi).save(os.path.join(a.out, 'p%02d.png' % i))
    print('LibreOffice 미리보기(대략): %d쪽 → %s' % (doc.page_count, a.out))
except ImportError:
    print('PDF만 만들었다(쪽 그림은 PyMuPDF 필요): %s' % os.path.join(a.out, 'doc.pdf'))
print('주의: 한컴 배치와 다르다. 최종 확인·제출본은 remote_render.py로.')
