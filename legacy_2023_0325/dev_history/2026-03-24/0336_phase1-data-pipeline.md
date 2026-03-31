# Phase 1 데이터 파이프라인 재구축

- **날짜**: 2026-03-24
- **계획 파일**: `.claude/plans/composed-inventing-tide.md`
- **목적**: 기존 `load_datasets.py`(MT-Eval, StructFlowBench, LIFBench 로드)를 연구 계획에 맞는 RuLES/IFEval/ShareGPT/MultiChallenge 파이프라인으로 전면 교체

---

## 작업 내역

### Step 1: `configs/preprocess.yaml` 생성
- 모든 경로, 데이터셋 다운로드 설정, 전처리 파라미터, 실험 설계 변수를 중앙 관리
- 토큰 카운팅 설정 (tiktoken cl100k_base)
- 실험 변수: turn_counts, difficulty, rule_count, probe_intensity, token_length

### Step 2: `src/data_pipeline/token_utils.py` 생성
- `count_tokens()`, `is_in_token_range()` 함수
- tiktoken 인코딩 캐싱 구현

### Step 3: `src/data_pipeline/download_datasets.py` 생성
- RuLES: git sparse-checkout (scenarios/ + data/)
- IFEval: HuggingFace `datasets` 라이브러리
- ShareGPT: `huggingface_hub` 파일 다운로드
- MultiChallenge: 로컬 GoogleCloud 경로에서 `shutil.copy2`
- 이미 다운로드된 경우 skip 로직 포함

### Step 4a: `src/data_pipeline/preprocess_rules.py` 생성
- RuLES repo의 JSONL 테스트 케이스에서 system prompt + probe 추출
- `SCENARIO_RULE_COUNT` 매핑으로 rule_count 분류 (few/many)
- `SCORING_CHECKS` 매핑으로 programmatic scoring 설명 생성
- 시나리오별 max_probes_per_scenario 제한

### Step 4b: `src/data_pipeline/preprocess_ifeval.py` 생성
- IFEval 프롬프트에서 format constraint → system prompt rule 분리
- task 부분 → probe message 분리 (heuristic sentence boundary detection)
- auto-scorable 타입만 필터 (18개 instruction type)
- `SCORING_FUNCTIONS` 매핑으로 rule-based scoring 설명

### Step 4c: `src/data_pipeline/preprocess_sharegpt.py` 생성
- human/user 메시지만 추출
- 품질 필터: 최소 길이, 영어 비율 체크, exclude_patterns
- 토큰 길이 bin 분류: short (50-150tok), long (350-650tok)
- bin별 max_turns_per_bin 제한, 별도 JSONL 출력

### Step 4d: `src/data_pipeline/preprocess_multichallenge.py` 생성
- CONVERSATION에서 user+assistant 턴 쌍 추출
- TARGET_QUESTION 제외 (RuLES/IFEval probe로 대체)
- AXIS 카테고리별 필터 및 분포 로깅

### Step 5: `src/data_pipeline/generate_experiment_cases.py` 생성
- 전처리 데이터 조합으로 ~104개 실험 케이스 생성
  - Case 1 (baseline, turns=0): 4조건
  - Case 2 (normal/ShareGPT): 32조건
  - Case 3 (hard/MultiChallenge): 16조건
  - × 2 probes = ~104 케이스
- `intermediate_turns_type`: "none" / "user_only" / "full"
- 최종 스키마에 scoring 정보 포함

### Step 6: 기존 파일 업데이트
- `load_datasets.py` → 파이프라인 오케스트레이터로 전면 교체 (download → preprocess × 4 → generate)
- `src/data_pipeline/CLAUDE.md` → 새 파일 목록, 인터페이스, CLI 명령어 반영
- `src/CLAUDE.md` → Common Data Schema를 experiment case 스키마로 교체
- `CLAUDE.md` (root) → Key File Map 확장, Data Flow 다이어그램 갱신

### Step 7: 의존성
- `requirements.txt` 신규 생성
- `tiktoken` 설치 (venv pip shebang 한글 경로 문제 → `python -m pip`으로 우회)
- 기존 `datasets`, `huggingface_hub`, `pyyaml`은 이미 설치됨

---

## 생성/수정 파일 목록

### 신규 (8개)
```
configs/preprocess.yaml
src/data_pipeline/token_utils.py
src/data_pipeline/download_datasets.py
src/data_pipeline/preprocess_rules.py
src/data_pipeline/preprocess_ifeval.py
src/data_pipeline/preprocess_sharegpt.py
src/data_pipeline/preprocess_multichallenge.py
src/data_pipeline/generate_experiment_cases.py
requirements.txt
```

### 수정 (4개)
```
src/data_pipeline/load_datasets.py      ← 전면 교체
src/data_pipeline/CLAUDE.md             ← 반영
src/CLAUDE.md                           ← 스키마 교체
CLAUDE.md                               ← File Map + Data Flow
```

---

## 실행 방법
```bash
# 전체 파이프라인
./capstone_dev/bin/python -m src.data_pipeline.load_datasets --config configs/preprocess.yaml

# 다운로드 skip
./capstone_dev/bin/python -m src.data_pipeline.load_datasets --config configs/preprocess.yaml --skip-download

# 개별 모듈
./capstone_dev/bin/python -m src.data_pipeline.download_datasets --config configs/preprocess.yaml
./capstone_dev/bin/python -m src.data_pipeline.preprocess_rules --config configs/preprocess.yaml
# ... (각 모듈 동일 패턴)
```

## 참고
- RuLES repo 구조 조사: scenarios는 Python 클래스 (BaseScenario), 테스트 데이터는 JSONL (data/{basic,redteam}/*.jsonl)
- venv 경로에 한글이 포함되어 pip 직접 실행 불가 → `python -m pip` 패턴 사용 필요
- 아직 실제 다운로드/실행은 하지 않음 (코드 작성만 완료)
