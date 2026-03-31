# acpx Gemini Session Reconnect 문제 분석 및 조치

- **날짜**: 2026-03-31
- **증상**: `eval_cycle.sh` 실행 시 `agent needs reconnect` 무한 대기, exit code 3
- **영향**: Gemini 평가자 워크플로우 중단 → 평가 없이 작업 진행 (규칙 위반)

---

## 1. 증상 상세

```
[acpx] session evaluator (...) · agent needs reconnect
[client] initialize (running)
[client] session/new (running)
```

eval_cycle.sh가 `acpx --approve-all gemini -s evaluator ...`를 실행하면:
1. 기존 세션이 있어도 `agent needs reconnect` 상태
2. `session/new` 단계에서 멈춤
3. JSON 파싱 오류 동반:
   ```
   Failed to parse JSON message: Created execution plan for SessionEnd...
   SyntaxError: Unexpected token 'C', "Created ex"... is not valid JSON
   ```

## 2. 원인 분석

### 2.1 직접 원인: hcom gemini-sessionend hook의 JSON 출력 오염

acpx v0.4.0은 hook 실행 시 stdout을 JSON으로 파싱하려고 시도함. 
`hcom gemini-sessionend` hook이 사람이 읽을 수 있는 일반 텍스트를 stdout에 출력 →
acpx JSON 파서가 실패 → 세션 종료/생성 과정이 비정상 완료.

```
Failed to parse JSON message: "Created execution plan for SessionEnd: 1 hook(s)..."
```

이 메시지는 **hcom이 stdout에 출력한 디버그 로그**가 acpx의 JSON 파서에 들어간 것.

### 2.2 간접 원인: 세션 상태 불일치

위 hook 오류로 인해:
1. 이전 세션이 정상적으로 닫히지 않음 (zombie session)
2. 새 세션 생성 시 이전 세션 정리 과정에서 다시 hook 오류 발생
3. 새 세션이 `needs reconnect` 상태로 생성됨

### 2.3 환경 정보

| Component | Version |
|-----------|---------|
| acpx | 0.4.0 |
| hcom | 0.7.7 |
| node | v25.8.2 |
| gemini CLI | /opt/homebrew/bin/gemini |

## 3. 재현 조건

1. hcom gemini-sessionend hook이 등록된 상태에서
2. `acpx gemini sessions new --name evaluator` 실행
3. hook이 stdout에 텍스트 로그 출력 → JSON 파싱 실패

## 4. 해결 방법

### 4.1 즉시 조치 (수동 복구)

```bash
# 1. 기존 세션 모두 정리
acpx gemini sessions close evaluator

# 2. 새 세션 생성 (hook 오류는 무시됨 — 세션 자체는 생성됨)
acpx gemini sessions new --name evaluator

# 3. 직접 호출 (eval_cycle.sh 대신)
acpx --approve-all gemini -s evaluator "평가 프롬프트"
```

**위 방법으로 2026-03-31 22:45에 성공적으로 Gemini 평가 수행 확인.**

### 4.2 근본 조치 (hook 수정)

hcom의 `gemini-sessionend` hook이 stdout에 디버그 로그를 출력하지 않도록 수정 필요.

**방법 A**: hcom hook의 stdout을 /dev/null로 리다이렉트
```bash
# eval_cycle.sh 내에서 세션 생성/종료 시
acpx gemini sessions close evaluator 2>/dev/null || true
acpx gemini sessions new --name evaluator 2>/dev/null
```

**방법 B**: hcom gemini-sessionend hook 자체를 비활성화 (hcom 설정에서)
```bash
hcom hooks disable gemini-sessionend  # if supported
```

**방법 C**: acpx 업데이트 확인
```bash
npm update -g acpx  # 0.4.0 → 최신 버전에서 수정되었을 수 있음
```

### 4.3 eval_cycle.sh 개선

현재 스크립트는 세션 오류 시 exit 3으로 종료. 개선안:

```bash
# ensure_session() 함수 내에 재시도 로직 추가
ensure_session() {
    # 기존 세션 닫기 (오류 무시)
    acpx gemini sessions close "$SESSION_NAME" 2>/dev/null || true
    sleep 1
    
    # 새 세션 생성 (stderr의 JSON 파싱 오류 무시)
    acpx gemini sessions new --name "$SESSION_NAME" 2>/dev/null
    
    # 역할 부여
    acpx --approve-all --timeout 60 gemini -s "$SESSION_NAME" "$ROLE_PROMPT" 2>/dev/null
    echo "0" > "$COUNTER_FILE"
}
```

## 5. 예방 조치

1. **eval_cycle.sh 실행 실패 시**: 즉시 사용자에게 보고하고 작업 중단 (CLAUDE.md 절대 규칙)
2. **acpx 버전 모니터링**: `acpx --version`으로 주기적 확인
3. **수동 fallback**: eval_cycle.sh 실패 시 위 4.1의 수동 복구 절차 사용
