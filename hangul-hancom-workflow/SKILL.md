---
name: hangul-hancom-workflow
description: Windows에서 한글(.hwpx) 문서를 고치고, 설치된 한컴오피스(한글)를 숨긴 채 실제 쪽 배치로 확인하고, 한컴이 직접 저장한 최종본과 PDF를 내는 절차와 도구. 보고서·논문·공문·서식의 문구 수정, 표 열 너비·낱말 끊김, 캡션과 표 쪽 나눔, 각주(주→각주), 목차 쪽 번호, 코드 상자 고정폭 글꼴, 스타일 글자 크기, 글꼴 설치, 피드백 반영 후 hwpx+pdf 제출에 쓴다. Use when editing .hwpx files on Windows with Hancom Office installed and the result must be verified with Hancom's own rendering (hidden COM automation, no screen or keyboard use).
---

# 한글 문서: 고치기 → 한컴으로 확인 → 한컴이 저장한 최종본

이 스킬의 도구는 `scripts/`에 있다(아래 `S` = 이 스킬 폴더의 `scripts`). 모두 Python 3(+lxml, PyMuPDF(fitz), Pillow, pywin32, psutil, fontTools)와 Windows의 한컴오피스 한글이 있어야 한다.
겪어서 알게 된 함정과 수치는 `references/lessons.md`에 있다. 처음 쓰는 문서라면 그 파일을 먼저 읽는다.

## 지켜야 할 것

1. **사용자 화면을 쓰지 않는다.** 한컴은 `render.py`로만 띄운다(숨은 COM 인스턴스, 임시 사본). 키보드·마우스 입력, 창을 앞으로 가져오기 금지. 보안 창('모두 허용')은 `hwp_allow.ps1`이 창을 커서 밑으로 옮겨 메시지로 누른다.
2. **사용자가 띄운 한컴에 손대지 않는다.** `render.py`는 새 Hwp.exe가 생기지 않으면 아무것도 하지 않고 멈춘다. 그 한컴을 닫거나 그 문서를 저장하지 않는다.
3. **한컴이 열고 있는 파일에 쓰지 않는다.** 한 번에 렌더 하나만. 렌더 중에는 hwpx를 쓰지 않는다.
4. **원본은 두고 새 파일에 쓴다.** 고치기 전에 백업을 남긴다(`작업/형식_<단계>전.hwpx` 같은 이름).
5. **최종 파일은 한컴이 저장한 것.** XML로 고친 파일을 그대로 내지 않는다. `render.py --resave`가 만든 파일을 낸다(줄 배치·스타일을 한컴이 다시 써서 다른 한글 판에서도 같게 보인다).
6. **한글 기능을 쓴다.** 빈 줄·빈칸 대신 문단 간격, 손으로 친 번호 대신 각주·스타일·자동 번호, '다음 문단과 함께', 오른쪽 자동 탭+채움 문자(목차), 수식 개체.
7. **눈으로 확인한 것만 됐다고 말한다.** 도구 결과와 쪽 그림을 함께 본다. 확인하지 못한 것은 그렇다고 적는다.

## 기본 절차

```
0. 읽기      python S/dump.py 문서.hwpx --cells --styles > dump.txt     (문단 번호·스타일·글, 표 칸)
1. 렌더(전)  python S/render.py 문서.hwpx review_0                       (쪽 수, 글꼴 경고, p01.png …)
2. 고치기    python S/edit.py 문서.hwpx work.hwpx edits.json             (문구·코드 줄·쪽 나눔·스타일·각주)
             python S/fit_table.py work.hwpx work.hwpx --caption "[표 2] "  (표 열 너비·줄 나눔, 필요할 때)
             python S/overflow.py work.hwpx                               (칸·코드 상자에서 넘칠 줄 미리 찾기)
3. 렌더      python S/render.py work.hwpx review_1
4. 목차      python S/toc_pages.py work.hwpx review_1/doc.pdf             (목차 쪽 번호를 PDF에 맞춰 적음)
5. 재저장    python S/render.py work.hwpx review_2 --resave saved.hwpx    (한컴이 저장한 최종 후보 + PDF)
6. 점검      python S/toc_pages.py saved.hwpx review_2/doc.pdf --check   (differing 0이어야 함)
             python S/check.py saved.hwpx review_2/doc.pdf --compare review_0/doc.pdf
7. 눈 점검   바뀐 쪽 그림(review_2/pNN.png)을 직접 본다. 전체 쪽은 하위 에이전트에게 맡겨도 된다(아래 '쪽 점검 지시').
8. 내기      saved.hwpx → 최종 이름으로 복사, review_2/doc.pdf → 같은 이름 .pdf. 기록(수정 대조표·handoff)에 무엇을 왜 바꿨는지 적는다.
```

- 4에서 쪽 번호를 바꾸면 3→4를 한 번 더 해 바뀐 쪽 번호로 배치가 달라지지 않았는지 본다(보통 그대로).
- PDF 표지 글꼴이 바뀌어 나오면 `render.py`가 경고한다 → `fonts.ps1 -Reload`(풀린 사용자 글꼴 다시 올리기) 뒤 5를 다시.
- 실행은 `python -I`(다운로드한 파일 옆의 모듈을 불러오지 않게). 셸에서 파이프를 쓸 때는 `set -o pipefail`.
- 스크립트 파일은 Write 도구로 만든다. Bash heredoc 안의 Python 문자열에 `\n`, `\\`를 넣으면 깨진다.

## edits.json (edit.py)

```json
[
 {"op":"replace", "find":"성능이 크게 향상되었다.", "replace":"성능이 조금 향상되었다.", "why":"피드백 2번"},
 {"op":"keep_with_next", "para":"[표 4]는 다음과 같다", "nth":-1},
 {"op":"style", "name":"코드", "font":"돋움체", "align":"LEFT", "line_spacing":160, "monospace":true},
 {"op":"split_line", "line":"    gap = (a - b).days if (a and b) else 0", "lines":["    gap = ((a - b).days", "           if (a and b) else 0)"]},
 {"op":"note_to_footnote", "para":"주: 자료는", "anchor":"[표 1] ", "strip":"주:"},
 {"op":"para_shape", "para":"[표 1] ", "like":"[표 3] "},
 {"op":"table_page_break", "value":"TABLE"},
 {"op":"page_break_before", "para":"부록 2. 설정", "nth":-1},
 {"op":"renumber_footnotes"}
]
```
- `replace`의 find는 문서 전체(본문·표 칸·각주)에서 **정확히 한 번** 나와야 한다. 짧고 유일한 글로 잡는다. 줄바꿈·탭·각주 표시를 사이에 두고 갈린 글은 못 바꾼다(오류로 멈춤 → 더 짧게 잡는다).
- 같은 글이 목차와 본문에 다 있으면 문단 op는 `nth:-1`(마지막=본문)을 쓴다.
- 문구를 바꾸면 문단 길이가 달라져 쪽이 밀린다. 바꾼 뒤 반드시 렌더·목차·점검을 다시 한다.
- 표·그림 번호를 바꾸면 뒤 조사도 바꾼다(`hwpx_lib.josa('[표 7]', ('은','는'))` → '은').

## 자주 하는 일

| 하고 싶은 것 | 방법 |
|---|---|
| 피드백 문장 반영 | 근거(표·수치)를 문서에서 먼저 확인 → `replace`. 피드백이 준 문장도 문서 수치와 맞는지 본다. |
| 제목·설명을 표와 같은 쪽에 | 설명 문단에 `keep_with_next`(제목은 보통 이미 켜져 있음). 쪽 나눔 강제는 마지막 수단. |
| 표 칸에서 낱말이 중간에 끊김 | `overflow.py`로 찾기 → `fit_table.py --caption …`(필요하면 `--rejoin`, `--width`, `--safe`). |
| 캡션이 표와 다른 쪽 | `check.py`가 '!'로 알림. 상자·표를 줄이거나(줄 간격·글자) 앞 문단에 `keep_with_next`. 한 쪽을 거의 채우는 상자에 `keep_with_next`를 걸면 캡션만 다음 쪽으로 갈 수 있다. |
| 긴 표에서 한 행이 두 쪽에 갈림 | `table_page_break` TABLE(셀 단위로 나눔). 제목 행 반복(repeatHeader)도 확인. |
| '주:'를 각주로 | `note_to_footnote`, 이어서 캡션 문단 모양을 다른 캡션과 같게 `para_shape`. |
| 코드 상자 정리 | `style` op로 고정폭(돋움체)·왼쪽 정렬·줄 간격 → `overflow.py --style 코드`로 넘칠 줄 → `split_line`으로 괄호 안에서 나누고 이어지는 줄은 여는 괄호 다음 칸에 맞춤. |
| 표 글자 크기만 줄이기(예 11→10.5pt) | 스타일 '표본문'의 글자 모양과 표 칸 run이 쓰는 글자 모양을 바꾼다. 표 밖에서도 쓰는 모양이면 복제(`Hwpx.clone_char_pr`). 줄 수에 맞춘 행 높이는 새 줄 높이로(lessons.md). |
| 목차 | 한글 '차례 만들기'와 같은 모양(스타일 '차례 n', 제목 → 오른쪽 자동 탭+채움 → 쪽 번호)을 두고 `toc_pages.py`로 번호만 맞춘다. 자동화로 '차례 만들기'를 부르지 않는다(한컴 2020에서 죽는다). |
| 글꼴 설치 | 공식 배포처에서 받아 `fonts.ps1 -Install <폴더>`(관리자 권한 없이 사용자 글꼴). 내려받기 전에 사용자에게 묻는다. |
| 웹 채팅·업로드 창에 파일 넣기 | 브라우저의 '파일 올리기'로 열린 Windows '열기' 창에 `pick_file.ps1 -Path <파일>`(키 입력 없이 경로 넣고 '열기'). 올리기(보내기)는 사용자 요청이 있을 때만. |

## 쪽 점검 지시(하위 에이전트용)

전체 쪽 눈 점검은 값싼 모델에 맡겨도 된다. 지시에 넣을 것: 쪽 그림 경로(p01~pNN), 읽기 전용, 모든 그림을 열었는지 첫 줄에 보고, 찾을 결함 목록(제목만 쪽 끝에 남음 / 표·그림과 캡션 분리 / 행이 두 쪽에 갈림 / 글자 잘림·겹침·칸 밖으로 나감 / 낱말 중간 끊김 / 각주 표시와 같은 쪽 각주 번호 / 쪽 번호 순서 / 40% 넘게 빈 쪽), 이번에 바뀐 곳, 비교할 이전 판 그림 폴더. 결과 가운데 '새로 생긴 결함'은 직접 그림을 열어 확인한 뒤 고친다.

## 도구 목록

| 파일 | 하는 일 |
|---|---|
| `hwpx_lib.py` | 공통: 열기/저장(zip 순서 유지), 문단·표·캡션 찾기, 문단·글자 모양 복제, 글꼴 추가, 실제 여백 읽기(`para_margins`), 각주 추가·번호, 문구 바꾸기, 글자 폭(`Meter`), 조사(`josa`) |
| `render.py` | 숨은 한컴 → PDF·쪽 그림, `--resave`로 한컴 재저장. 시작할 때 사용자 글꼴을 이번 세션에 다시 올리고, 그래도 없는 글꼴은 경고 |
| `render_server.py` | 다른 컴퓨터(라즈베리 파이 등, `hangul-hwpx-pi` 스킬)가 공유 폴더·SSH로 맡긴 hwpx를 render.py로 렌더해 PDF·재저장본을 돌려줌 |
| `hwp_allow.ps1` | 한컴 자동화 보안 창 '모두 허용' 누르기(render.py가 부름) |
| `edit.py` | JSON 수정 적용 |
| `fit_table.py` | 표 열 너비·칸 줄 나눔 |
| `overflow.py` | 표 칸·코드 상자에서 넘칠 줄 미리 찾기 |
| `toc_pages.py` | 목차 쪽 번호 적기/비교 |
| `check.py` | 캡션 번호·캡션 분리·각주·쪽 번호·빈 쪽·긴 표 점검, 이전 PDF와 비교 |
| `dump.py` | 문단·표 칸·스타일 내보내기 |
| `fonts.ps1` | 사용자 글꼴 설치·다시 올리기·목록 |
| `pick_file.ps1` | Windows '열기' 창에 파일 경로 넣기 |
