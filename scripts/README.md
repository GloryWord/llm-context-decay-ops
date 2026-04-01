# scripts/ — 오케스트레이터 전환 가이드

## 현재 구조

```
scripts/
├── README.md           ← 이 파일
├── claude_only/        ← Claude Code 오케스트레이터 전용
└── gemini_only/        ← Gemini 오케스트레이터 전용 (현재 사용 중)
```

---

## 오케스트레이터별 사용법

### 🟣 현재: Gemini 오케스트레이터 (Claude Code 플랜 미구독 기간)

```bash
# 기본 평가 (Composer2 + GPT-5.4 병렬)
bash scripts/gemini_only/eval_all.sh <산출물경로>

# 최종 검증 (GPT-5.4 Extra High 추가, 고비용)
bash scripts/gemini_only/eval_all.sh --final <산출물경로>

# 특정 모델만
bash scripts/gemini_only/eval_cursor.sh --model composer-2 <산출물경로>

# 비상 리셋
bash scripts/gemini_only/eval_reset_session.sh
```

**역할 구조:**
```
Gemini (오케스트레이터)
  └── Cursor Agent (평가자)
        ├── composer-2  → 코드 구조/아키텍처
        └── gpt-5.4    → 논리 정합성
```

---

### 🟡 복구 시: Claude Code 오케스트레이터 (플랜 재구독 후)

```bash
# 기본 평가 (Gemini CLI + Cursor 병렬)
bash scripts/claude_only/eval_all.sh <산출물경로>

# 최종 검증
bash scripts/claude_only/eval_all.sh --final <산출물경로>

# Gemini 세션 리셋 (비상용)
bash scripts/claude_only/eval_reset_session.sh
```

**역할 구조:**
```
Claude Code (오케스트레이터)
  ├── Gemini CLI via acpx (평가자 1) → 완결성/학문적 엄밀성
  └── Cursor Agent (평가자 2)
        ├── composer-2  → 코드 구조/아키텍처
        └── gpt-5.4    → 논리 정합성
```

---

## 전환 방법

### Gemini → Claude Code (플랜 복구 시)

1. **CLAUDE.md 경로 확인**: 평가 스크립트 경로가 `scripts/claude_only/`인지 확인
2. **acpx Gemini 세션 초기화**: `bash scripts/claude_only/eval_reset_session.sh`
3. **테스트 실행**: `bash scripts/claude_only/eval_all.sh docs/outputs/final_report.md`

### Claude Code → Gemini (플랜 중단 시)

1. **GEMINI.md 경로 확인**: 평가 스크립트 경로가 `scripts/gemini_only/`인지 확인
2. **테스트 실행**: `bash scripts/gemini_only/eval_all.sh docs/outputs/final_report.md`

---

## 주의사항

> **⚠️ Gemini self-call 금지**
> Gemini가 오케스트레이터일 때, acpx를 통해 자기 자신(Gemini)을 평가자로 호출하면 무한루프가 발생합니다.
> `gemini_only/` 스크립트는 이를 방지하도록 설계되었습니다.
