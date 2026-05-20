# Cursor 고대비(High Contrast) 설정 추가

- **작업 일시**: 2026-04-28 18:01
- **작업 목적**: 사용자의 요청에 따라 Cursor 에디터 요소 간의 구분을 확실히 하고 텍스트의 가독성을 높이기 위해 고대비 스타일을 부여.
- **작업 내용**:
  - `~/Library/Application Support/Cursor/User/settings.json` 파일 내 `workbench.colorCustomizations` 수정.
  - `[Visual Studio Light]` 및 `[Evergruv (Everforest) Light]` 테마에 `contrastBorder`(`#4a5d4e`, 짙은 올리브 그린) 및 `editor.foreground`(`#1c2b1e`, 더 짙은 올리브 텍스트색) 추가.
- **결과**: 테마의 고유한 톤앤매너를 유지하면서도 테두리 구분선과 본문 텍스트의 대비를 명확히 하여 시인성이 향상됨.
