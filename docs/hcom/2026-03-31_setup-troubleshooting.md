# hcom 인프라 초기 구축 기록 (2026-03-31)

## 환경

- hcom 0.7.7
- macOS (Darwin 25.3.0)
- 터미널: iTerm (자동 감지)
- 지원 도구: Claude ✓, Gemini ✓, Codex ✗, OpenCode ✗

## 초기 상태에서 발견된 문제

### 1. 에이전트 `jongwoong` launch_failed 상태

`hcom list` 실행 시 아래와 같이 출력:

```
○ jongwoong     3m ago: launch_failed
```

이전에 에이전트를 띄우려다 실패한 잔여 상태였음.

**조치:**

- `hcom kill jongwoong` → 실패 (`No tracked PID for 'jongwoong'`)
  - PID가 추적되지 않는 에이전트는 `kill`로 제거 불가
- `hcom stop jongwoong` → 성공
  - launch_failed 등 PID 없는 에이전트는 **`stop`으로 정리**해야 함

### 2. 현재 세션이 hcom에 미등록 상태

`hcom list` 출력에서:

```
Your name: (not participating)
```

Claude Code 세션이 hcom 네트워크에 참여하지 않은 상태.

**조치:**

- `hcom start` 실행 → `nipe`라는 이름으로 등록 완료
- 이후 `hcom list`에서 `▶ nipe active` 확인

### 3. `hcom help` 명령어 오류

```
Error: Unknown command 'help'
```

**원인:** hcom은 `help` 서브커맨드를 지원하지 않음.

**올바른 사용법:**

```bash
hcom --help              # 전체 사용법
hcom <command> --help    # 개별 커맨드 도움말
hcom run docs            # 공식 문서 전체 출력
```

## 정상 구축 절차 (정리)

```bash
# 1. 상태 확인
hcom --version
hcom status

# 2. 잔여 에이전트 정리 (launch_failed 등)
hcom stop <agent_name>

# 3. 현재 세션 등록
hcom start
# → 자동으로 4글자 이름 부여됨 (예: nipe)

# 4. Gemini 에이전트 런치
hcom 1 gemini --tag eval --name <my_name>
# → 새 터미널 창에서 Gemini CLI 실행됨

# 5. 런치 완료 대기
hcom events launch --name <my_name>
# → ready 상태 확인

# 6. 전체 에이전트 상태 확인
hcom list -v --name <my_name>
```

## 최종 구축 결과

| 에이전트 | 이름 | 도구 | 태그 | 상태 |
|---------|------|------|------|------|
| Claude Code | nipe | claude | - | ▶ active |
| Gemini CLI | eval-hana | gemini | eval | ◉ listening |

## 통신 명령어

```bash
# Claude → Gemini
hcom send @hana --name nipe -- "메시지 내용"

# Gemini → Claude
hcom send @nipe -- "메시지 내용"

# 전체 브로드캐스트
hcom send --name nipe -- "메시지 내용"
```

## Gemini YOLO 모드 설정 (권한 승인 자동화)

Gemini CLI를 `--yolo` 플래그로 런치하면, `hcom send` 등 도구 실행 시
"Allow execution?" 승인 대기 없이 자동 승인된다.

**문제**: YOLO 없이 런치하면 Gemini가 hcom send를 실행할 때마다 블로킹됨.
수동으로 `hcom term inject <name> '2' --enter`로 승인해야 했음.

**해결**:

```bash
# 방법 1: 글로벌 설정
hcom config gemini_args "--yolo"

# 방법 2: 런치 시 직접 전달
hcom 1 gemini --tag eval --yolo
```

**주의**: `--yolo`는 도구 자동 승인이지, 메시지 입력 자동 제출이 아님.
hcom 메시지가 Gemini 입력창에 도착한 후 `hcom term inject <name> --enter`는 여전히 필요.

## 주의사항

- `--name <자신의이름>` 플래그를 모든 hcom 명령에 붙여야 함 (세션 식별용)
- 에이전트 이름은 4글자 CVCV 패턴으로 자동 생성됨
- `--tag` 사용 시 에이전트 이름이 `tag-name` 형태가 됨 (예: `eval-hana`)
- 태그 프리픽스로 그룹 전체에 메시지 가능: `hcom send @eval- -- "메시지"`
- Gemini는 반드시 `--yolo` 모드로 런치할 것 (승인 블로킹 방지)
