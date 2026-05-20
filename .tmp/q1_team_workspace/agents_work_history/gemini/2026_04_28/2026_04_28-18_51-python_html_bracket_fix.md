# Python 스크립트 내 HTML 구문 괄호 버그 수정

- **작업 일시**: 2026-04-28 18:51
- **작업 목적**: Python 파일 내부에서 HTML 형태의 문자열을 작성 시, 여는 괄호(`<`) 하나만 입력한 직후 해당 기호가 하얗게 깨지는 문제 해결. (괄호 페어링에서 "Unexpected Bracket"으로 인식되어 흰색으로 빠지거나, 중첩 스코프인 `text.html.basic`이 하얗게 렌더링되는 현상)
- **작업 내용**:
  - `editorBracketHighlight.unexpectedBracket.foreground` 속성을 짙은 녹색(`#3b533e`)으로 강제 지정하여 예상치 못한/닫히지 않은 괄호 기호가 하얗게 뜨는 것을 방지.
  - TextMate Rules에 `punctuation.definition.tag.begin.html`, `text.html.basic`, `invalid.illegal.unrecognized-tag.html` 등 파이썬 내장 HTML 파서가 뱉어내는 디테일한 에러/일반 스코프들을 모두 잡아 짙은 녹색으로 할당.
- **결과**: Python 문자열 내에서 `<` 하나만 입력하고 대기 중인 상태여도 흰색이 아닌 정상적인 올리브색/녹색으로 선명하게 표시됨.
