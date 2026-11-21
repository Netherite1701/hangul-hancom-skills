# -*- coding: utf-8 -*-
"""한컴 렌더·재저장을 한컴이 있는 Windows PC에 맡긴다(그 PC에서 render_server.py가 돌고 있어야 한다).
표준 라이브러리만 쓴다(라즈베리 파이에 추가 설치 없이 돈다).

사용:
  공유 폴더(동기화·네트워크 공유)  python3 remote_render.py <문서.hwpx> <출력폴더> --share /mnt/hwpshare [--no-resave] [--pngs] [--dpi 110]
  SSH(Windows의 OpenSSH 서버)      python3 remote_render.py <문서.hwpx> <출력폴더> --ssh user@pc --share C:/hwpshare [...]

결과(출력폴더): doc.pdf(한컴이 만든 PDF), saved.hwpx(한컴이 다시 저장한 hwpx, --no-resave가 아니면), pNN.png(--pngs), log.txt, status.json.
최종본은 saved.hwpx다. 끝나면 status.json의 ok·warnings(빠진 글꼴 등)를 확인한다.
"""
import argparse, json, os, shutil, subprocess, sys, time, uuid

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('out')
ap.add_argument('--share', required=True, help='공유 폴더(이 컴퓨터에서 보이는 경로, --ssh면 Windows 쪽 경로 예: C:/hwpshare)')
ap.add_argument('--ssh', help='user@host (Windows OpenSSH 서버)')
ap.add_argument('--no-resave', action='store_true'); ap.add_argument('--pngs', action='store_true')
ap.add_argument('--dpi', type=int, default=110); ap.add_argument('--timeout', type=int, default=900)
ap.add_argument('--keep', action='store_true', help='PC 쪽 outbox의 결과를 지우지 않는다')
a = ap.parse_args()
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

if not os.path.isfile(a.src):
    sys.exit('문서가 없다: %s' % a.src)
jid = time.strftime('%Y%m%d%H%M%S') + '_' + uuid.uuid4().hex[:8]
spec = {'resave': not a.no_resave, 'pngs': a.pngs, 'dpi': a.dpi}
os.makedirs(a.out, exist_ok=True)


def ssh(cmd):
    """Windows 쪽 PowerShell 명령. 출력 문자열."""
    p = subprocess.run(['ssh', '-o', 'BatchMode=yes', a.ssh, 'powershell', '-NoProfile', '-Command', cmd],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise SystemExit('ssh 실패: %s' % (p.stderr.strip() or p.stdout.strip()))
    return p.stdout.strip()


def scp(src, dst, recursive=False):
    p = subprocess.run(['scp', '-q', '-o', 'BatchMode=yes'] + (['-r'] if recursive else []) + [src, dst],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise SystemExit('scp 실패: %s' % p.stderr.strip())


start = time.time()
if not a.ssh:                                   # 공유 폴더
    inbox, outbox = os.path.join(a.share, 'inbox'), os.path.join(a.share, 'outbox')
    assert os.path.isdir(inbox) and os.path.isdir(outbox), ('공유 폴더에 inbox/outbox가 없다(PC에서 render_server.py를 먼저 켠다): %s' % a.share)
    # 문서를 .part로 다 쓴 뒤 → 설정 → 이름 바꾸기. 서버는 .hwpx와 .json이 함께 있을 때만 집어 간다.
    shutil.copy(a.src, os.path.join(inbox, jid + '.hwpx.part'))
    json.dump(spec, open(os.path.join(inbox, jid + '.json'), 'w', encoding='utf-8'))
    os.replace(os.path.join(inbox, jid + '.hwpx.part'), os.path.join(inbox, jid + '.hwpx'))
    done = os.path.join(outbox, jid, 'status.json')
    print('작업 %s 넣음 → PC의 렌더를 기다린다' % jid, flush=True)
    while not os.path.exists(done):
        if time.time() - start > a.timeout:
            raise SystemExit('시간 초과: PC에서 render_server.py가 돌고 있는지, 동기화가 되는지 확인')
        time.sleep(2)
    time.sleep(1)                                # 동기화 폴더라면 다른 파일이 따라오도록 잠깐
    for f in os.listdir(os.path.join(outbox, jid)):
        shutil.copy(os.path.join(outbox, jid, f), a.out)
    if not a.keep:
        shutil.rmtree(os.path.join(outbox, jid), ignore_errors=True)
else:                                           # SSH
    share = a.share.replace('\\', '/').rstrip('/')
    tmpjson = os.path.join(a.out, jid + '.json')
    json.dump(spec, open(tmpjson, 'w', encoding='utf-8'))
    scp(tmpjson, '%s:%s/inbox/%s.json' % (a.ssh, share, jid)); os.remove(tmpjson)
    scp(a.src, '%s:%s/inbox/%s.hwpx.part' % (a.ssh, share, jid))
    ssh("Rename-Item -LiteralPath '%s/inbox/%s.hwpx.part' -NewName '%s.hwpx'" % (share, jid, jid))
    print('작업 %s 보냄 → PC의 렌더를 기다린다' % jid, flush=True)
    while ssh("Test-Path -LiteralPath '%s/outbox/%s/status.json'" % (share, jid)) != 'True':
        if time.time() - start > a.timeout:
            raise SystemExit('시간 초과: PC에서 render_server.py가 돌고 있는지 확인')
        time.sleep(3)
    tmpdir = os.path.join(a.out, '_' + jid)
    scp('%s:%s/outbox/%s' % (a.ssh, share, jid), tmpdir, recursive=True)
    for f in os.listdir(tmpdir):
        shutil.move(os.path.join(tmpdir, f), os.path.join(a.out, f))
    os.rmdir(tmpdir)
    if not a.keep:
        ssh("Remove-Item -LiteralPath '%s/outbox/%s' -Recurse -Force" % (share, jid))

st = json.load(open(os.path.join(a.out, 'status.json'), encoding='utf-8'))
print('결과(%.0f초): %s' % (time.time() - start, json.dumps(st, ensure_ascii=False)))
print('받은 파일:', ', '.join(sorted(os.listdir(a.out))))
sys.exit(0 if st.get('ok') else 1)
