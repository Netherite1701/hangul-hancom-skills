# 라즈베리 파이 설치

Raspberry Pi OS(64비트, Debian 기반) 기준. 다른 데비안·우분투 계열도 같다.

## 1. 스킬 옮기기

Windows PC의 `C:\Users\<사용자>\.claude\skills\hangul-hwpx-pi` 폴더를 파이의 `~/.claude/skills/hangul-hwpx-pi`로 복사한다(Claude Code를 파이에서 쓸 때). 스크립트만 쓸 거면 아무 폴더나 된다.

## 2. Python 패키지(가상 환경)

```bash
sudo apt install python3-venv fontconfig
python3 -m venv ~/.venvs/hwpx
~/.venvs/hwpx/bin/pip install lxml pymupdf pillow
```
이후 `python3` 대신 `~/.venvs/hwpx/bin/python`으로 실행한다. `remote_render.py`는 표준 라이브러리만 써서 시스템 `python3`로도 돈다.

## 3. 글꼴(글자 폭 계산과 미리보기용)

`fit_table.py`·`overflow.py`는 문서가 쓰는 글꼴 파일로 글자 폭을 잰다. 함초롬체는 Windows PC의 `C:\Windows\Fonts\HAN*.ttf`(함초롬돋움·바탕), 코드용 돋움체는 `gulim.ttc`(Windows 글꼴, 파이로 옮길 수 있는지는 사용 조건을 확인), KoPub은 kopus.org 배포본.
```bash
mkdir -p ~/.local/share/fonts && cp HAN*.ttf ~/.local/share/fonts/ && fc-cache -f
fc-list | grep -i -E "함초롬|HCR"          # 한글 이름이 보여야 한다
```

## 4. (선택) LibreOffice 대략 미리보기

```bash
sudo apt install libreoffice-writer libreoffice-h2orestart
```
`libreoffice-h2orestart`가 저장소에 없으면(배포판 판에 따라 없음) H2Orestart 확장(.oxt)을 받아 `unopkg add <파일>.oxt`. Java(JRE)가 필요하다.

## 5. 점검

```bash
P=~/.venvs/hwpx/bin/python; S=~/.claude/skills/hangul-hwpx-pi/scripts
$P -c "import lxml, fitz, PIL; print('ok')"
$P -c "import sys; sys.path.insert(0,'$S'); import hwpx_lib as h; print(h.font_index().get('함초롬돋움'))"
$P $S/dump.py 문서.hwpx | head
python3 $S/remote_render.py 문서.hwpx /tmp/r --share <공유폴더>     # PC의 render_server.py가 켜져 있어야 함
```
