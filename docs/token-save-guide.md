# Claude Code 비용 최적화 가이드

> **출처**: [공식 문서 — Manage costs effectively](https://docs.anthropic.com/en/docs/claude-code/costs), [Model configuration](https://code.claude.com/docs/en/model-config), [Best practices](https://code.claude.com/docs/en/best-practices), [Subagents](https://code.claude.com/docs/en/sub-agents)

---

## 핵심 수치

| 항목 | 값 |
|---|---|
| 개발자 1인 평균 일일 비용 | ~$6 (90%가 $12 이하) |
| Sonnet 4.6 월 평균 | ~$100–200/개발자 |
| 캐시 히트 비용 | 일반 입력 가격의 **10%** |
| 캐시 유효 시간 | 마지막 요청 후 **5분** |
| Auto-compaction 트리거 | 컨텍스트의 ~83.5% 도달 시 |
| Autocompact 버퍼 | ~33K 토큰 (200K 윈도우 기준) |

---

## 1. 프롬프트 캐싱 (자동)

Claude Code는 **프롬프트 캐싱**과 **auto-compaction**을 기본 활성화하여 비용을 자동 최적화한다.

- 캐시 히트는 입력 가격의 **10%**만 과금된다. 캐시 적중률 90%라면, 원래 $100 세션이 약 $19로 줄어든다.
- 5분 이상 유휴 상태면 캐시가 만료된다. **작업 중에는 연속적으로 사용**하라.
- 캐시가 만료된 상태에서 `/compact`을 호출하면 전체 컨텍스트를 원가로 재처리하게 되므로, 오래 쉬고 돌아왔다면 `/compact` 대신 **`/clear`로 새 세션**을 시작하는 편이 저렴하다.
- 디버깅/벤치마킹 목적으로 캐싱을 비활성화하려면:

```bash
# 전역 비활성화
export DISABLE_PROMPT_CACHING=1
# 모델별 비활성화
export DISABLE_PROMPT_CACHING_SONNET=1
```

> **규칙**: 활성 세션 중 컨텍스트가 길어졌다 → `/compact`. 휴식 후 복귀 → `/clear`.

---

## 2. 컨텍스트 관리 — 가장 큰 비용 레버

토큰 비용은 컨텍스트 크기에 비례한다. 메시지를 보낼 때마다 **전체 이전 컨텍스트가 재전송**된다.

### /clear — 작업 전환 시 필수

```
/clear
```

관련 없는 작업으로 전환할 때 반드시 사용. 이전 작업의 컨텍스트는 이후 모든 메시지에서 토큰을 낭비한다.

- `/clear` 전에 `/rename`으로 세션 이름을 지정하면 나중에 `/resume`으로 복귀 가능.

### /compact — 대화 압축

```
/compact Focus on code samples and API usage
```

- 커스텀 지시를 추가하여 요약 시 보존할 내용을 지정할 수 있다.
- auto-compaction은 컨텍스트의 ~83.5% 도달 시 자동 발동되지만, 그 전에 수동으로 실행하는 것을 권장한다.
- `/compact`은 대화를 요약하여 새 세션에 프리로드하므로, 핵심 결정과 현재 상태는 유지된다.

### /btw — 컨텍스트에 남지 않는 빠른 질문

```
/btw 이 함수의 시그니처가 뭐지?
```

답변이 dismissible 오버레이에 표시되어 **대화 이력에 추가되지 않는다**. 간단한 확인에 적합.

---

## 3. 모델 선택 — 작업에 맞는 모델 사용

```
/model sonnet    # 일상 작업의 80% (기본값으로 사용)
/model opus      # 복잡한 아키텍처·추론이 필요할 때만
/model haiku     # 단순 읽기, 구문 확인 등
```

**Sonnet은 Opus 대비 1/5 비용**으로 대부분의 코딩 작업을 처리한다. Opus 출력 토큰은 Haiku의 약 19배 비용이다.

### opusplan 하이브리드 모드

```
/model opusplan
```

- Plan 모드에서는 Opus로 추론, 코드 생성 시에는 자동으로 Sonnet으로 전환.
- Opus 수준의 사고력이 필요하되 비용을 통제하고 싶을 때 최적.

### 1M 컨텍스트 윈도우

Opus 4.6과 Sonnet 4.6은 1M 토큰 컨텍스트를 지원한다.

```
/model opus[1m]
/model sonnet[1m]
```

- 200K 한계에 의한 빈번한 compaction이 문제라면 고려. 추가 요금 없음.
- 필요 없으면 `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`로 비활성화.

---

## 4. Extended Thinking 조절

Thinking 토큰은 **출력 토큰으로 과금**되며, 기본 budget이 수만 토큰에 달할 수 있다.

### Effort 레벨 (Opus 4.6 / Sonnet 4.6)

| 레벨 | 용도 | 설정 |
|---|---|---|
| `low` | 단순 작업, 파일 읽기, 포맷 변경 | `/effort low` |
| `medium` | 일반 코딩 (Opus 기본값) | `/effort medium` |
| `high` | 복잡한 디버깅·설계 | `/effort high` |
| `max` | 최대 추론 (Opus만, 세션 한정) | `/effort max` |

```bash
# 환경변수로 고정 budget 사용 (adaptive thinking 비활성화 시)
export CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1
export MAX_THINKING_TOKENS=8000
```

- `/config`에서 thinking 자체를 비활성화하는 것도 가능.
- thinking 파라미터 변경 시 캐시 breakpoint가 무효화되므로 주의.

---

## 5. CLAUDE.md 최적화

CLAUDE.md는 **매 세션 시작 시 자동 로드**되어 전체 대화 동안 컨텍스트를 점유한다.

- **50줄 이하**를 목표로 하되, 전체 메모리 파일 합산 **10,000 토큰 이하** 유지.
- 100줄 ≈ 4,000 토큰 ≈ 200K 윈도우의 2%.
- 세부 문서는 CLAUDE.md에 직접 넣지 말고 **Skills로 분리**하여 on-demand 로드.
- Claude가 소스 파일을 직접 읽어 파악할 수 있는 정보는 CLAUDE.md에서 제외.
- `.claudeignore` 파일로 불필요한 파일(node_modules, dist, lock 파일 등)의 인덱싱을 차단.

```gitignore
# .claudeignore
node_modules/
dist/
*.lock
*.min.js
__pycache__/
```

---

## 6. 서브에이전트 활용 — 컨텍스트 격리

서브에이전트는 **독립된 컨텍스트 윈도우**에서 실행되어, 대량 출력이 메인 대화를 오염시키지 않는다.

```
서브에이전트를 사용해서 인증 시스템의 토큰 갱신 방식을 조사해줘.
```

- 테스트 실행, 문서 수집, 로그 분석 등 **대량 출력 작업**에 특히 효과적.
- 서브에이전트가 수십 개 파일을 읽어도 메인 대화에는 **요약만 반환**.
- 빌트인 서브에이전트: **Explore**(Haiku, 읽기 전용), **Plan**(계획 모드 리서치), **general-purpose**(전체 도구 접근).

### 커스텀 서브에이전트로 비용 절감

```yaml
# .claude/agents/quick-reviewer.md
---
name: quick-reviewer
description: 코드 리뷰 (use proactively)
model: haiku
tools: Read, Grep, Glob
---
보안 취약점과 코드 스타일을 점검하라.
```

저비용 모델(Haiku)로 라우팅하여 반복 작업의 비용을 대폭 절감할 수 있다.

---

## 7. 프롬프트 작성 원칙

| 나쁜 예 | 좋은 예 |
|---|---|
| "인증 흐름의 버그를 고쳐줘" | "src/auth/token.py의 refresh_token()에서 만료 체크 로직 수정" |
| "전체 테스트 실행해줘" | "auth 모듈 테스트만 실행해줘" |
| "이 코드 설명해줘" | "이 함수의 시간 복잡도와 엣지 케이스를 설명해줘" |

- **파일 경로와 함수명을 명시**하면 Claude가 코드베이스 탐색에 쓰는 토큰을 절약.
- 탐색 범위가 넓어질 것 같으면 서브에이전트에 위임.
- **Plan 모드**(Shift+Tab × 2)로 코드 작성 전 계획을 먼저 세우면 잘못된 방향의 토큰 낭비 방지.

---

## 8. 환경변수 & 자동화

```bash
# 비필수 백그라운드 모델 호출 억제 (제안·팁 등)
export DISABLE_NON_ESSENTIAL_MODEL_CALLS=1

# auto-compaction 트리거 비율 조정 (1-100)
export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80

# 출력 토큰 한도 (기본 32K, 너무 높이면 컨텍스트 여유 감소)
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=16000
```

### Hooks로 토큰 사전 절감

`PreToolUse` 훅을 활용하여 커맨드 출력 길이를 제한하거나, 불필요한 파일 읽기를 차단할 수 있다.

---

## 9. 비용 모니터링

| 명령어 | 용도 |
|---|---|
| `/cost` | 현재 세션 토큰 사용량 + 비용 |
| `/stats` | 사용 패턴 (구독자용) |
| `/context` | 컨텍스트 윈도우 내역 (시스템 프롬프트, 도구, 메모리, 메시지 각각) |
| Console Usage 페이지 | 조직 전체 비용·캐시 효율 |

Status line에 토큰 사용량을 상시 표시하도록 설정하는 것도 좋다.

---

## 10. 일일 워크플로우 요약

```
1. 세션 시작 → /model sonnet, /effort medium (또는 low)
2. 작업 A 시작 → 구체적 프롬프트, 파일 경로 명시
3. 컨텍스트 비대 → /compact (캐시 유효 시)
4. 작업 A 완료 → /rename → /clear
5. 작업 B 시작 → 새 컨텍스트에서 진행
6. 복잡한 설계 필요 시 → /model opus (또는 opusplan)
7. 대량 탐색 필요 시 → 서브에이전트 위임
8. 복귀 시 → /resume session-name
```

---

*이 문서는 Claude Code 공식 문서(2026년 3월 기준)를 바탕으로 작성되었습니다.*