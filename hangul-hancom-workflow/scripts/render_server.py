# -*- coding: utf-8 -*-
"""렌더 서버(Windows, 한컴이 있는 PC): 공유 폴더에 들어온 hwpx를 render.py로 렌더해 결과를 돌려준다.
라즈베리 파이 같은 다른 컴퓨터가 한컴 렌더·재저장을 맡길 때 쓴다(파이 쪽은 hangul-hwpx-pi 스킬의 remote_render.py).

사용: python render_server.py <공유폴더> [--once] [--poll 5]
  <공유폴더>/inbox/<작업id>.json + <작업id>.hwpx  →  <공유폴더>/outbox/<작업id>/ 에 doc.pdf, saved.hwpx(요청 시), pNN.png(요청 시), log.txt,
  마지막에 status.json({"ok": true/false, "pages": n, ...}).
- 한 번에 한 작업. 작업 json에서 받는 값은 resave(bool), pngs(bool), dpi(int)뿐이다(그 밖의 값은 무시).
- 들어온 파일은 hwpx만 연다(이름이 작업id 꼴이고 zip이며 header.xml이 있는지 확인).
- --once: 지금 있는 작업만 처리하고 끝낸다. 없으면 --poll 초마다 본다(Ctrl+C로 끝냄).
- 공유 폴더는 이 PC와 맡기는 컴퓨터만 쓸 수 있는 곳이어야 한다: 거기에 파일을 넣을 수 있는 누구나 이 PC의 한컴으로 문서를 열게 할 수 있다.
"""
import argparse, json, os, re, shutil, subprocess, sys, time, traceback, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('share'); ap.add_argument('--once', action='store_true')
ap.add_argument('--poll', type=float, default=5)
a = ap.parse_args()
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
inbox, outbox, work = (os.path.join(a.share, d) for d in ('inbox', 'outbox', 'work'))
for d in (inbox, outbox, work):
    os.makedirs(d, exist_ok=True)
JOB = re.compile(r'^[0-9A-Za-z_-]{6,64}$')


def ready_jobs():
    out = []
    for f in sorted(os.listdir(inbox)):
        jid, ext = os.path.splitext(f)
        if ext == '.hwpx' and JOB.match(jid) and os.path.exists(os.path.join(inbox, jid + '.json')):
            out.append(jid)
    return out


def run(jid):
    src_in, spec_in = os.path.join(inbox, jid + '.hwpx'), os.path.join(inbox, jid + '.json')
    wd = os.path.join(work, jid); od = os.path.join(outbox, jid)
    shutil.rmtree(wd, ignore_errors=True); shutil.rmtree(od, ignore_errors=True)
    os.makedirs(wd); os.makedirs(od)
    src = os.path.join(wd, 'src.hwpx')
    shutil.move(src_in, src)
    try:
        spec = json.load(open(spec_in, encoding='utf-8'))
    except Exception:
        spec = {}
    os.remove(spec_in)
    resave, pngs = bool(spec.get('resave', True)), bool(spec.get('pngs', False))
    dpi = int(spec.get('dpi', 110)) if str(spec.get('dpi', 110)).isdigit() else 110
    status = {'ok': False, 'job': jid}
    try:
        z = zipfile.ZipFile(src); names = z.namelist(); z.close()
        assert 'Contents/header.xml' in names, 'hwpx가 아님(header.xml 없음)'
        cmd = [sys.executable, '-I', os.path.join(HERE, 'render.py'), src, os.path.join(wd, 'r'), '--dpi', str(dpi)]
        if resave:
            cmd += ['--resave', os.path.join(wd, 'saved.hwpx')]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
        log = p.stdout + p.stderr
        open(os.path.join(od, 'log.txt'), 'w', encoding='utf-8').write(log)
        assert p.returncode == 0 and os.path.exists(os.path.join(wd, 'r', 'doc.pdf')), 'render.py 실패(log.txt)'
        shutil.copy(os.path.join(wd, 'r', 'doc.pdf'), od)
        if resave:
            shutil.copy(os.path.join(wd, 'saved.hwpx'), od)
        if pngs:
            for f in sorted(os.listdir(os.path.join(wd, 'r'))):
                if f.endswith('.png'):
                    shutil.copy(os.path.join(wd, 'r', f), od)
        m = re.search(r'pages\(pdf\) (\d+)', log)
        status.update(ok=True, pages=int(m.group(1)) if m else None,
                      warnings=[l for l in log.splitlines() if l.startswith('WARNING')],
                      fonts=next((l[len('PDF fonts: '):] for l in log.splitlines() if l.startswith('PDF fonts: ')), ''))
    except Exception as e:
        status['error'] = '%s: %s' % (type(e).__name__, e)
        open(os.path.join(od, 'log.txt'), 'a', encoding='utf-8').write('\n' + traceback.format_exc())
    tmp = os.path.join(od, 'status.json.tmp')
    json.dump(status, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
    os.replace(tmp, os.path.join(od, 'status.json'))           # 결과 파일을 다 쓴 뒤 마지막에
    shutil.rmtree(wd, ignore_errors=True)
    print(time.strftime('%H:%M:%S'), jid, 'ok' if status['ok'] else status.get('error'), flush=True)


print('render_server: watching', inbox, flush=True)
while True:
    jobs = ready_jobs()
    for jid in jobs:
        run(jid)
    if a.once and not ready_jobs():
        break
    if not jobs:
        time.sleep(a.poll)
