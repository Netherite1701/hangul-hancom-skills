---
name: hangul-hwpx-pi
description: 라즈베리 파이(ARM 리눅스)나 다른 리눅스에서 한글(.hwpx) 문서를 고치고 점검하는 절차와 도구. 한컴오피스가 없는 곳이므로 문구·각주·스타일·표 열 너비 수정과 넘칠 줄 점검은 여기서 하고, 실제 쪽 배치 확인·PDF·한컴 재저장 최종본은 한컴이 있는 Windows PC(render_server.py)에 맡긴다. PC 없이 볼 때는 LibreOffice+H2Orestart 대략 미리보기. Use on Raspberry Pi / Linux to edit .hwpx files and delegate Hancom rendering to a Windows PC.
---

# 라즈베리 파이에서 한글 문서 다루기

`S` = 이 스킬 폴더의 `scripts`. 함정과 수치는 `references/lessons.md`(Windows 스킬과 같은 내용), 설치는 `references/setup.md`.

## 무엇을 어디서 하나

| 일 | 파이 | 한컴 PC 필요 |
|---|---|---|
| 글 읽기·문단 찾기 (`dump.py`) | 됨 | |
| 문구·코드 줄·쪽 나눔 설정·스타일·주→각주 (`edit.py`) | 됨 | |
| 표 열 너비·줄 나눔 (`fit_table.py`), 넘칠 줄 찾기 (`overflow.py`) | 됨(글꼴 파일이 파이에 있어야 함) | |
| 실제 쪽 배치·PDF·한컴 재저장본 | **안 됨**(ARM용 한컴 없음) | `remote_render.py` → PC의 `render_server.py` |
| 목차 쪽 번호 (`toc_pages.py`), 최종 점검 (`check.py`) | 됨(한컴 PDF를 받아서) | PDF만 |
| 대략 미리보기 (`preview_lo.py`) | LibreOffice+H2Orestart가 있으면 | |

**최종본은 언제나 PC의 한컴이 저장한 `saved.hwpx`와 그 `doc.pdf`.** LibreOffice 미리보기는 쪽 배치가 한컴과 달라서 쪽 나눔·캡션 분리·낱말 끊김·목차 번호 판단에 쓰지 않는다.

## 기본 절차

```
0. 읽기     python3 S/dump.py 문서.hwpx --cells --styles > dump.txt
1. 고치기   python3 S/edit.py 문서.hwpx work.hwpx edits.json
            python3 S/overflow.py work.hwpx   →  필요하면  python3 S/fit_table.py work.hwpx work.hwpx --caption "[표 2] "
2. 렌더     python3 S/remote_render.py work.hwpx r1 --share <공유폴더> --pngs        (또는 --ssh user@pc --share C:/hwpshare)
3. 목차     python3 S/toc_pages.py work.hwpx r1/doc.pdf          (번호가 바뀌면 2를 한 번 더)
4. 재저장   python3 S/remote_render.py work.hwpx r2 --share <공유폴더> --pngs   →  r2/saved.hwpx, r2/doc.pdf
5. 점검     python3 S/toc_pages.py r2/saved.hwpx r2/doc.pdf --check     (differing 0)
            python3 S/check.py r2/saved.hwpx r2/doc.pdf --compare r1/doc.pdf
            r2/status.json의 warnings(빠진 글꼴)와 fonts를 본다. 바뀐 쪽 그림(r2/pNN.png)을 직접 본다.
6. 내기     r2/saved.hwpx → 최종 이름.hwpx, r2/doc.pdf → 같은 이름.pdf
```
- `remote_render.py`는 기본으로 재저장본(saved.hwpx)까지 받는다. PDF만 필요하면 `--no-resave`.
- 렌더 한 번: 2쪽 문서 약 10초, 64쪽 논문 약 20초(+공유 폴더 동기화 시간).
- `edits.json` 형식과 op 목록은 `edit.py` 맨 위 설명(Windows 스킬 SKILL.md와 같음): replace / split_line / keep_with_next / page_break_before / style / table_page_break / note_to_footnote / para_shape / renumber_footnotes.

## 지켜야 할 것

1. 원본은 두고 새 파일에 쓴다. 고치기 전 백업.
2. 공유 폴더는 이 파이와 그 PC만 쓰는 곳으로. 거기에 파일을 넣을 수 있는 누구나 PC의 한컴으로 문서를 열게 할 수 있다.
3. PC 쪽 설정(SSH 서버 켜기, 네트워크 공유 만들기, 방화벽)은 사용자가 직접 한다. 시스템 설정을 대신 바꾸지 않는다.
4. 글꼴 파일을 파이로 옮길 때는 배포 조건을 지킨다(함초롬체·KoPub은 무료 배포 글꼴, 그 밖의 상용 글꼴은 옮기지 않는다).
5. 확인한 것만 됐다고 말한다. 렌더를 PC에 맡기지 못했으면 "한컴 배치는 확인하지 못함"이라고 적는다.

## PC 쪽(한 번만)

한컴이 있는 Windows PC에 `hangul-hancom-workflow` 스킬이 있어야 한다. 그 PC에서:
```
python <hangul-hancom-workflow>\scripts\render_server.py C:\hwpshare
```
- 공유 방법 하나를 고른다: ① 동기화 폴더(Syncthing, 구글 드라이브 데스크톱 등) ② 네트워크 공유를 파이에 마운트 ③ SSH(Windows '선택적 기능'의 OpenSSH 서버를 사용자가 켜고 키 로그인 설정, 공유 폴더 경로는 영문).
- 서버는 한 번에 한 작업, hwpx만 연다. 사용자가 그 PC에서 한컴을 쓰고 있어도 따로 숨은 한컴을 띄우며, 사용자 한컴에 붙으면 작업을 멈추고 오류를 돌려준다.

## 확인한 범위(2026-11-20)

- 파이 쪽 도구는 리눅스(WSL Ubuntu, x86_64, Python 3.14)에서 시험했다: fc-list 글꼴 찾기(함초롬체 한글 이름), 공유 폴더로 PC 렌더(2쪽·64쪽, 잘못된 파일·없는 파일 처리).
- **실제 라즈베리 파이(ARM)에서는 아직 돌려 보지 않았다.** 쓰는 것은 표준 Python과 lxml·PyMuPDF·Pillow(모두 ARM 리눅스용 배포가 있음)라 그대로 돌 것으로 보지만, 처음 쓸 때 setup.md의 점검 명령으로 확인한다.
- SSH 방식(`--ssh`)과 `preview_lo.py`는 시험하지 못했다(이 PC에 SSH 서버·LibreOffice 없음).
