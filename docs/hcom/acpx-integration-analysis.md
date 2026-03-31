# acpx 통합 분석: 현재 워크플로우 개선 가능성

> 작성일: 2026-03-31
> 작성자: hiro (Claude Code)
> 최종 수정: 2026-03-31

## 1. acpx란?

[acpx](https://github.com/openclaw/acpx)는 **Agent Client Protocol (ACP)**의 headless CLI 클라이언트다. AI 코딩 에이전트(Claude Code, Gemini CLI, Codex, OpenCode, Pi 등)와 **프로토콜 기반 구조화된 통신**을 제공한다. PTY(터미널) 스크래핑 대신 타입이 지정된 ACP 메시지(thinking, tool calls, diffs)를 사용한다.

- **설치**: `npm install -g acpx@latest` 또는 `npx acpx@latest`
- **요구사항**: Node.js 22.12.0+
- **상태**: Alpha (인터페이스 변경 가능)
- **지원 에이전트**: Claude Code, Gemini CLI, Codex, OpenCode, Pi, Kimi

참조:
- [GitHub: openclaw/acpx](https://github.com/openclaw/acpx)
- [ACP Agents 문서](https://docs.openclaw.ai/tools/acp-agents)
- [Gemini 3 + OpenClaw + ACPX Agent Mesh 구축](https://timtech4u.medium.com/building-an-ai-agent-mesh-with-gemini-3-openclaw-and-acpx-7b6ab5f1cbf4)

---

## 2. 현재 워크플로우 (hcom) vs acpx 비교

| 항목 | hcom (현재) | acpx |
|------|------------|------|
| **통신 방식** | PTY 기반 hook 주입 | ACP 프로토콜 기반 구조화 메시지 |
| **터미널 필요** | 예 (iTerm/kitty 등 별도 창) | 아니오 (headless) |
| **메시지 전달** | hook이 입력창에 텍스트 주입 | 프로토콜로 직접 프롬프트 전송 |
| **Enter 주입 문제** | 있음 (Gemini에서 수동 Enter 필요) | 없음 (프롬프트가 프로토콜로 직접 전달) |
| **세션 지속성** | 프로세스 종속 (stale 발생) | 파일 기반 (`~/.acpx/`) — 세션 생존 |
| **구조화된 출력** | 텍스트 기반 (파싱 필요) | 타입 지정 메시지 (thinking/tool_call/diff) |
| **에이전트 관리** | TUI 대시보드 + kill/stop | 세션 기반 관리 (inspect/history) |
| **설정** | `~/.hcom/config.toml` | `~/.acpx/config.json` + 프로젝트별 설정 |
| **성숙도** | v0.7.7 (안정적) | Alpha (인터페이스 변경 가능) |

---

## 3. 현재 워크플로우에서 겪은 hcom의 문제점

오늘(2026-03-31) 실제 작업 중 발견한 문제:

### 3.1 Gemini Enter 주입 필수
hcom이 Gemini 입력창에 메시지를 넣지만, 자동 제출이 안 됨.
매번 `hcom term inject hana --enter`를 수동으로 실행해야 했음.

### 3.2 세션 Stale 문제
Claude Code 세션(nipe)이 대화 중 stale 처리됨.
재등록 시 새 이름(hiro)이 배정되어 메시지 라우팅 혼란 발생.

### 3.3 권한 승인 블로킹
Gemini가 `hcom send` (heredoc 포함)를 실행하려 할 때 권한 승인 대기에 블로킹됨.
수동으로 `hcom term inject hana '2' --enter`로 승인해야 했음.

### 3.4 메시지 전달 확인의 어려움
메시지가 실제로 전달되었는지 확인하려면 `hcom term`, `hcom events` 등을 반복 조회해야 함.

---

## 4. acpx가 해결할 수 있는 부분

| 현재 문제 | acpx 해결 방식 | 기대 효과 |
|----------|-------------|----------|
| Enter 주입 필수 | 프로토콜 기반 직접 프롬프트 전송 — PTY 불필요 | 메시지 전달 자동화 100% |
| 세션 Stale | 파일 기반 세션 지속성 (`~/.acpx/`) | 대화 중 세션 유실 방지 |
| 권한 승인 블로킹 | headless 모드 — 터미널 UI 승인 불필요 | 자동화 파이프라인 중단 없음 |
| 전달 확인 어려움 | 구조화된 응답 메시지 (타입 지정) | 프로그래밍적 응답 파싱 가능 |

---

## 5. acpx가 해결하지 못하는 부분

| 항목 | 설명 |
|------|------|
| **실시간 양방향 대화** | acpx는 요청-응답 모델. hcom의 실시간 양방향 메시징(send/listen)과 이벤트 구독은 지원하지 않음 |
| **에이전트 간 직접 통신** | hcom은 에이전트끼리 직접 @멘션으로 대화 가능. acpx는 오케스트레이터→에이전트 단방향 |
| **Alpha 안정성** | 프로덕션 의존 시 breaking change 리스크 |
| **TUI 대시보드** | hcom의 에이전트 상태 모니터링 TUI가 없음 |

---

## 6. 터미널 구성: 몇 개가 필요한가?

### 핵심: **1개만 필요하다**

acpx는 **headless**다. Gemini를 백그라운드 프로세스로 실행하고 ACP 프로토콜로 통신한다.
hcom처럼 별도 터미널 창에 Gemini를 띄울 필요가 없다.

| 도구 | 필요 터미널 수 | 구성 |
|------|-------------|------|
| hcom (이전) | 2~3개 | Claude Code 1개 + Gemini 1개 + 모니터링 1개 |
| **acpx (현재)** | **1개** | Claude Code 터미널에서 acpx로 Gemini headless 호출 |

```
┌──────────────────────────────────────┐
│  터미널 1: Claude Code (유일한 터미널)  │
│                                      │
│  사용자 ↔ Claude Code ↔ acpx ↔ Gemini │
│                          (headless)   │
│                                      │
│  Claude Code가 작업 완료할 때마다      │
│  acpx 명령어로 Gemini에 평가 요청      │
│  → 응답이 동기식으로 돌아옴             │
└──────────────────────────────────────┘
```

---

## 7. 사용자가 해야 할 것 (단계별)

### 사용자의 행동은 딱 2가지뿐이다:

**Step 1.** 터미널을 열고 Claude Code를 실행한다.
```
claude
```

**Step 2.** 자연어로 작업을 지시한다.
```
"benchmark_reuse_mapping.md를 작성해줘"
```

**끝이다.** 이후 아래는 전부 Claude Code가 자동으로 처리한다:
- 작업 수행
- Gemini evaluator에게 평가 요청 (`bash scripts/eval_cycle.sh <산출물>`)
- 평가 결과 수신
- 피드백 반영
- 필요 시 Gemini context 자동 리셋

사용자는 acpx 명령어를 알 필요도, 입력할 필요도 없다.

### 내부 동작 흐름 (참고용)

```
사용자: "작업해줘"
    ↓
Claude Code: 작업 수행
    ↓
Claude Code: bash scripts/eval_cycle.sh <산출물>
    ↓  (내부에서 acpx가 Gemini를 headless로 호출)
    ↓  (15회 이상 평가했거나 응답 이상 시 자동으로 세션 리셋)
    ↓
Claude Code: 평가 결과 수신 → 피드백 반영
    ↓
Claude Code: 결과 보고
```

---

## 8. Context 관리 비교

### Claude Code vs Gemini CLI vs acpx 경유 Gemini

| 기능 | Claude Code | Gemini CLI (직접) | acpx 경유 Gemini |
|------|------------|------------------|-----------------|
| **Context 압축** | `/compact` (수동 + ~95%에서 자동) | `/compress` (수동 + 70%에서 자동) | 직접 지원 없음 |
| **Context 창** | 1M tokens (Opus 4.6) | 1M tokens (2.5 Pro) | 에이전트에 의존 |
| **수동 리셋** | 새 대화 시작 | `/compress` 또는 새 세션 | `sessions close` → `sessions new` |
| **메모리 지속** | CLAUDE.md (프로젝트별) | GEMINI.md (글로벌+프로젝트별) | 세션 파일 (~/.acpx/) |

### Gemini CLI `/compress` 명령어

Gemini CLI는 Claude Code의 `/compact`에 대응하는 **`/compress`** 명령어를 지원한다:
- 전체 대화 기록을 요약하여 교체
- **70% context 사용률에서 자동 발동** (Claude Code는 ~95%)
- 수동으로도 `/compress` 입력 가능
- 압축 후 GEMINI.md 메모리는 보존됨

### acpx에서의 Context 관리 전략: 자동 리셋

acpx는 `/compress`를 직접 호출할 수 없다. 대신 `eval_cycle.sh`가 **자동으로 context 포화를 감지하고 세션을 교체**한다.

**자동 리셋 조건 (둘 중 하나 충족 시):**
1. **평가 횟수 초과**: 누적 15회 이상 평가 시 자동 세션 교체
2. **응답 이상 감지**: 빈 응답, 타임아웃, 또는 응답 길이 50자 미만 시 세션 리셋 후 재시도

사용자가 직접 리셋할 필요 없다. Claude Code가 `eval_cycle.sh`를 실행하면 스크립트 내부에서 알아서 처리한다.

**평가자 역할에서 세션 교체가 안전한 이유:**
- 각 평가 요청은 독립적 (이전 평가 결과가 다음 평가에 영향 없음)
- 평가 기준은 역할 설정 프롬프트에 포함되어 있어 세션 교체 후에도 유지
- 1M tokens context에서 단일 문서 평가는 보통 10K tokens 미만

---

## 9. 실제 검증 결과 (2026-03-31)

acpx 0.4.0 + Gemini 3 (auto-gemini-3)으로 실제 워크플로우 검증 완료.

### 검증 1: one-shot 통신
```bash
acpx --approve-all gemini exec "테스트입니다. '응답 완료'라고만 답하세요."
# → "응답 완료" (Enter 주입 없이 즉시 응답)
```

### 검증 2: persistent session evaluator
```bash
# 세션 생성
acpx gemini sessions new --name evaluator

# 역할 설정
acpx --approve-all --timeout 60 gemini -s evaluator "당신은 evaluator입니다..."
# → "Ready"

# 문서 평가 요청 (파일 내용을 인라인으로 전달)
acpx --approve-all --timeout 120 gemini -s evaluator "다음 문서를 평가해주세요. $(cat docs/benchmark_reuse_mapping.md)"
# → 구조화된 한국어 평가 전문 수신 (완결성 최우수 / 엄밀성 우수 / 이슈 명확)
```

### 검증 결과

| 항목 | hcom (이전) | acpx (현재) |
|------|-----------|------------|
| Enter 수동 주입 | 매번 필요 | 불필요 |
| 승인 블로킹 | YOLO 없으면 블로킹 | --approve-all로 해결 |
| 응답 수신 | listen + 타임아웃 폴링 | 동기식 직접 반환 |
| 세션 지속성 | stale 발생 | 파일 기반 안정 |
| 총 수동 개입 횟수 | 평가 1회당 3~4회 | **0회** |

### 주의사항
- `-f` (파일 전달) 옵션은 빈 응답 반환하는 버그 있음 → `$(cat file)` 인라인 방식 사용
- hcom hook이 설치된 상태에서 JSON parse 경고 발생하지만 기능에 영향 없음
- `--timeout` 미지정 시 기본 300초 TTL 적용

---

## 10. 자동화 스크립트 (`scripts/eval_cycle.sh`)

**사용자가 이 스크립트를 직접 실행하지 않는다.**
Claude Code가 작업 완료 후 내부적으로 실행한다.

### 주요 기능
1. evaluator 세션이 없으면 자동 생성 + 역할 부여
2. 산출물을 Gemini에 전달하고 평가 결과 수신
3. **Context 자동 관리**: 15회 평가마다 세션 자동 리셋
4. **응답 이상 감지**: 빈 응답 / 50자 미만 응답 시 세션 리셋 후 재시도
5. 결과를 `docs/multi-agent-working-history/`에 자동 저장

### 별도 수동 리셋 스크립트 (`scripts/eval_reset_session.sh`)
비상 시 사용자가 직접 실행할 수 있으나, 정상 운영에서는 불필요.
`eval_cycle.sh`가 자동으로 리셋을 처리한다.
