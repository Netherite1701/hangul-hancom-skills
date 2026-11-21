# hangul-hancom-skills

한글(.hwpx) 문서를 고치고, 한컴오피스 한글이 실제로 그리는 쪽 배치로 확인한 뒤, 한컴이 직접 저장한 최종본과 PDF를 내기 위한 Claude Code 스킬 두 개.

Two Claude Code skills for editing Korean Hangul (.hwpx) documents and verifying them with Hancom Office's own rendering.

| 폴더 | 어디서 | 하는 일 |
|---|---|---|
| [`hangul-hancom-workflow`](hangul-hancom-workflow/SKILL.md) | Windows + 한컴오피스 한글 | 숨은 한컴으로 PDF·쪽 그림 만들기와 한컴 재저장(`render.py`), JSON으로 문구·각주·스타일·쪽 나눔 수정(`edit.py`), 표 열 너비·줄 나눔(`fit_table.py`), 넘칠 줄 찾기(`overflow.py`), 목차 쪽 번호(`toc_pages.py`), 최종 점검(`check.py`), 다른 컴퓨터의 렌더 요청 받기(`render_server.py`) |
| [`hangul-hwpx-pi`](hangul-hwpx-pi/SKILL.md) | 라즈베리 파이·리눅스 | 같은 편집·점검 도구 + 한컴 렌더를 Windows PC에 맡기기(`remote_render.py`, 공유 폴더 또는 SSH) + LibreOffice 대략 미리보기(`preview_lo.py`) |

## 설치

Claude Code의 사용자 스킬 폴더에 복사한다.

```bash
# Windows (Git Bash)
cp -r hangul-hancom-workflow ~/.claude/skills/
# 라즈베리 파이 / 리눅스
cp -r hangul-hwpx-pi ~/.claude/skills/
```

- Windows 쪽 필요한 것: 한컴오피스 한글, Python 3 + `lxml pymupdf pillow pywin32 psutil fonttools`.
- 파이 쪽은 [`hangul-hwpx-pi/references/setup.md`](hangul-hwpx-pi/references/setup.md).
- 겪어서 알게 된 함정과 수치(한컴 2020의 여백 저장 방식, 글자 폭, 표 너비, 보안 창 처리 등): [`references/lessons.md`](hangul-hancom-workflow/references/lessons.md).

## 원칙

- 사용자 화면·키보드·마우스를 쓰지 않는다(숨은 COM 인스턴스와 임시 사본만).
- 사용자가 띄워 둔 한컴에는 손대지 않는다(붙으면 멈춤).
- 최종 파일은 XML로 고친 파일이 아니라 한컴이 다시 저장한 파일.

## 확인 범위

- Windows 스킬: 한컴오피스 한글 2020에서 60쪽 넘는 문서로 시험. 도구만으로 손 편집 결과(본문 2,788문단, 64쪽 배치)를 그대로 다시 만드는 것을 확인했다.
- 파이 스킬: 리눅스(WSL Ubuntu)에서 공유 폴더 렌더 맡기기까지 시험. 실제 라즈베리 파이, SSH 방식, LibreOffice 미리보기는 아직 시험하지 않았다.
