# Phase 1 v2: Implementation — Project Aegis & Pipeline Refactor

**Date:** 2026-03-24
**Status:** Step 1-3 완료 (인프라 수정 + 규칙 세트 구현 + 케이스 생성기 수정)

---

## 수행한 작업

### Step 1: 인프라 수정

**configs/preprocess.yaml:**
- `experiment.turn_counts`: [0,2,4,6] → [0,2,4,6,8]
- `experiment.rule_count_levels`: [1,3,5,10,16] → [1,3,5,10,15,20]
- `tokenizer`: tiktoken cl100k_base → Qwen/Qwen3.5-9B AutoTokenizer
- `project_aegis` 섹션 신규 추가 (규칙 레벨별 매핑, probe 타겟)

**src/data_pipeline/token_utils.py:**
- tiktoken → transformers AutoTokenizer 전환 완료
- `TOKENIZERS_PARALLELISM=false` 설정 (Deadlock 방지)
- Singleton 캐싱 패턴 유지
- 기존 인터페이스(count_tokens, is_in_token_range) 호환

**호출부 수정:**
- `preprocess_sharegpt.py`: encoding_name → model_name 파라미터
- `compression/selective_context.py`: get_encoding → get_tokenizer
- `configs/compression.yaml`: tokenizer 설정 업데이트

**requirements.txt:** transformers, emoji 추가

**docs/phase1-research-plan.md:** v2 전면 개정 (타겟 모델, 변수 체계, Alignment Tax, 채점 방식)

### Step 2: Project Aegis 규칙 세트 구현

**src/data_pipeline/generate_multi_rule_probes.py — 전면 재작성:**
- 20개 도메인 응집형 규칙 정의 (AEGIS_RULES)
- 규칙 수 레벨별 매핑 (LEVEL_RULE_MAP, PROBE_TARGET_MAP)
- 규칙별 probe 질문 (basic 2개 + redteam 2개)
- 자동 채점 함수 10개 (SCORING_FUNCTIONS)
- `render_system_prompt()`: 규칙 ID 리스트 → system prompt 렌더링
- `score_rule()`: 규칙 ID + 응답 → 준수 여부 판정
- 실행 결과: 56개 probe 생성 (6 level × varying target rules × 2 intensity)

### Step 3: 케이스 생성기 수정

**src/data_pipeline/generate_experiment_cases.py — 전면 재작성:**
- `render_embedded_user_message()`: user_only 턴을 단일 메시지에 임베딩 (Chat Template 준수)
- `total_context_tokens`: 최종 렌더링 문자열 통째로 토큰화 (산술적 sum 금지)
- `probes_per_condition=2` 제한 적용
- Case 3 (Alignment Tax): MC 대화 + 규칙 수별 system prompt, task_accuracy 채점
- 실행 결과: 312건 (Baseline 24 + Normal 288, MC 미포함)

## 검증 결과
- Qwen 토크나이저 로드 정상 (vocab 248,044)
- 채점 함수 전체 테스트 통과 (Rule 1,3,5,14,20)
- 토큰 분포: min 122, max 4,662, mean 1,711 (turn 8 × long ≈ 4,662tok)
- 케이스 수: 계획의 24+288=312와 정확히 일치

## 수정된 파일 목록
1. `configs/preprocess.yaml`
2. `configs/compression.yaml`
3. `requirements.txt`
4. `docs/phase1-research-plan.md`
5. `src/data_pipeline/token_utils.py`
6. `src/data_pipeline/generate_multi_rule_probes.py`
7. `src/data_pipeline/generate_experiment_cases.py`
8. `src/data_pipeline/preprocess_sharegpt.py`
9. `src/compression/selective_context.py`
10. `src/data_pipeline/CLAUDE.md`
11. `src/CLAUDE.md`

## 다음 단계
- Step 2.5: Dry Run (10-20건 샘플 inference, 채점 regex 튜닝, Baseline Hard Limit 검증)
- Step 4: 408건 케이스 생성 (MC 데이터 포함)
- Step 5: Phase 1 v2 Inference
