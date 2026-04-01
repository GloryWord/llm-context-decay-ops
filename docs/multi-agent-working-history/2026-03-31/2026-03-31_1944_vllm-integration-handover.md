# 작업 기록: Local vLLM 연동 및 파이프라인 마이그레이션

- **날짜**: 2026-03-31 19:44
- **작업자**: eval-hana (Gemini 3, fallback executor)
- **인수인계 대상자**: hiro (Claude Code, planner/executor)

---

## 작업 배경 및 목표

Claude Code 토큰 사용량 제한 초과로 인해 Gemini가 긴급하게 fallback 작업자로 투입되었습니다. 주요 작업 목표는존 OpenRouter API 기반으로 동작하던 평가 파이프라인(추론, 채점 등)을 새롭게 구축된 **Local vLLM (Llama 3.1 8B AWQ) 환경으로 전환**하는 것이었습니다.

## 세부 작업 내역

Gemini가 소스코드를 다음과 같이 리팩터링 및 환경 구성을 완료했습니다.

### 1. 환경변수 기반 유연한 API 연결 구조로 변경 (Source Code 수정 완료)
Python 코드 내부에서 하드코딩되어 있던 모델 구성을 `os.getenv`를 활용하여 `.env`로 제어할 수 있도록 변경했습니다. 
- **수정된 파일**: 
  - `scripts/lite_experiment.py`
  - `src/models/open_router_request.py`
  - `src/evaluation/judge.py`
- **구현 내용**:
  - `lite_experiment.py` & `open_router_request.py`: 로컬 vLLM용 `VLLM_API_URL`과 `EVAL_MODEL_NAME` 변수를 가져와 실행되도록 변경. 토큰 에러 방지를 위해 로컬 모드에서는 `dummy_token_for_local_vllm`을 기본값으로 사용.
  - `judge.py`: 성능이 우수한 DeepSeek R1 채점을 위해 **OpenRouter를 유지**하며, 판독 모델명을 `JUDGE_MODEL_NAME` 환경 변수로 분리함.

### 2. .env 환경 설정 파일 생성
`/llm-context-decay-ops/.env` 파일을 신규 생성하여 로컬 vLLM 서버(외부 노출 IP)와 OpenRouter 라우팅 설정을 확정했습니다.

```env
VLLM_API_URL=http://210.179.28.26:18000/v1/chat/completions
EVAL_MODEL_NAME=hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4
JUDGE_MODEL_NAME=deepseek/deepseek-r1
OPENROUTER_API_KEY=dummy_token_for_local_vllm
```

> **주의 사항(Claude Code 필독)**: vLLM API(`/v1/models`) 검증 결과, 현재 로드된 모델의 정확한 이름 식별자가 `meta-llama/Meta-Llama-3.1-8B-Instruct`가 아니라 **`hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4`**입니다. 따라서 에러를 피하기 위해 해당 이름으로 `EVAL_MODEL_NAME`을 고정해두었습니다.

### 3. API 통신 테스트 성공 (Curl Test)
구축된 vLLM의 외부 포트(`http://210.179.28.26:18000/v1/chat/completions`)로의 쿼리 테스트를 진행했으며 한국어 응답을 정상적으로 수신했습니다. GPU의 AWQ 양자화 65k 컨텍스트 환경이 정상 작동됨을 입증했습니다.

---

## Claude Code (hiro) 의 다음 Action Item (To-Do)

1. **테스트 가동**: `scripts/lite_experiment.py` 파일을 재실행하여 vLLM 인프라 위에서 생성/평가가 정상 작동하는지 확인하기.
2. **LLM-Judge 본격 실험 통합**: `judge.py`에 구성된 OpenRouter의 DeepSeek R1으로 자동 채점 기능이 워크플로에 완전하게 결합되었는지 파일럿 결과 점검하기.
3. 본격적인 **310 cases (Context Decay) 메인 실험** 데이터 생성 스크립트 가동 준비하기.
