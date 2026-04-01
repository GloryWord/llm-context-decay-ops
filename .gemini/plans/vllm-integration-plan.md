# 작업 계획: Local vLLM 연동을 위한 평가 파이프라인 코드 수정

이 문서는 사용자의 "Claude Code Token 제한 초과" 및 "조만간 Local vLLM 세팅 완료" 상황에 대응하여, 기존 OpenRouter API 기반으로 동작하던 평가 파이프라인(추론, 채점, 요약 등)을 Local vLLM 환경으로 전환하기 위한 작업 계획을 담고 있습니다. 코드를 직접 수정하지 않고 벤치마크/채점 등 전체 파이프라인의 연동 구조 전환에 필요한 사항을 가이드로 정리했습니다.

---

## 1. 대상 파일 및 현재 구조 분석

프로젝트에서 언어 모델에 API 요청을 보내는 핵심 모듈들은 다음과 같이 `API_URL`, `API_KEY`, `MODEL` 등을 파일 스크립트 상단에 하드코딩하고, `aiohttp`를 이용해 비동기 HTTP 요청을 수행하고 있습니다.

**영향받는 주요 파일 목록:**
- `scripts/lite_experiment.py`: Lite 파일럿 실험 실행용 메인 스크립트
- `src/models/open_router_request.py`: 본격적인 다중 실험 케이스 추론용 API 클라이언트
- `src/evaluation/judge.py`: LLM-as-a-Judge로 작업 정확도(Task Accuracy)를 평가하는 채점 모듈
- `src/compression/summarize_turns.py`: 대화 컨텍스트 요약을 위해 LLM을 호출하는 스크립트

**기존 코드의 특징:**
- `API_URL = "https://openrouter.ai/api/v1/chat/completions"`가 하드코딩됨.
- `os.getenv("OPENROUTER_API_KEY")`를 필수로 요구하며, 없으면 요청을 중단함.
- `MODEL` 파라미터가 OpenRouter 포맷(예: `qwen/qwen3.5-9b` 또는 `meta-llama/llama-3.1-8b-instruct`)으로 지정되어 있음.

---

## 2. 코드 수정 방향 (Local vLLM 연동)

Local vLLM은 OpenAI API 호환 서버를 제공하므로, 기존 `aiohttp.ClientSession.post` 호출 구조 및 페이로드(`model`, `messages`, `temperature`, `max_tokens` 등)는 그대로 유지하면서 접속 정보만 수정하면 됩니다.

### [수정 사항 1] API Endpoint (URL) 변경
하드코딩된 OpenRouter URL 대신, 로컬에서 띄울 vLLM 서버의 기본 주소(일반적으로 `http://localhost:8000/v1/chat/completions`)로 요청을 보내도록 변경해야 합니다. 하드코딩된 변수를 수정하거나 환경변수를 도입하는 것을 권장합니다.

```python
# Before
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# After: 환경변수를 활용하여 유연하게 전환 가능하도록 권장
import os
API_URL = os.getenv("VLLM_API_URL", "http://localhost:8000/v1/chat/completions")
```

### [수정 사항 2] API 키(Token) 필수 의존성 제거
로컬 vLLM 서버는 기본적으로 인증(Authentication)을 요구하지 않지만, 기존 코드에 OpenAI API 스펙의 헤더 형식을 맞추기 위해 더미(Dummy) 토큰을 허용하도록 수정해야 합니다. 

```python
# Before
api_key = os.getenv("OPENROUTER_API_KEY", "")
if not api_key:
    logger.error("OPENROUTER_API_KEY not set")
    return  # 중단됨

# After: 로컬 환경에서는 토큰이 없어도 진행할 수 있도록 변경
api_key = os.getenv("LLM_API_KEY", "dummy_token_for_local_vllm")
```

### [수정 사항 3] Model Identity(모델명) 확인 및 변경
vLLM 명령어로 서버를 구동할 때 인자로 넘겨준 모델 경로(또는 식별자)가 API의 `model` 필드와 정확히 일치해야 합니다.

- 만약 로컬에 다운로드 받은 HuggingFace 캐시나 경로가 `/path/to/models/Llama-3.1-8B-Instruct` 라면, 코드의 `DEFAULT_MODEL` 또한 이와 일치해야 합니다. (또는 vLLM 서버 실행 시 `--served-model-name` 옵션을 통해 기존 코드에 하드코딩된 이름인 `meta-llama/llama-3.1-8b-instruct` 등으로 Alias를 지정하면 코드를 덜 수정해도 됩니다.)

---

## 3. 적용 프로세스 (추천 단계)

직접 코드 수정을 진행할 경우 아래의 순서로 진행하는 것을 권장합니다.

1. **중앙 집중식 환경변수 도입 (`.env` 도입이나 공통 Config 추가)**
   기존처럼 여러 파일에 분산된 `API_URL`을 수정하지 않고, `src/config.py` 혹은 환경변수를 참조하도록 하여 일괄적으로 OpenRouter/vLLM을 토글(Toggle)할 수 있게 만듭니다.
2. **`lite_experiment.py`부터 적용 및 격리 테스트 (파일럿)**
   전체 코드를 바꾸기 전에 `lite_experiment.py` 내부의 `API_URL`과 `api_key` 검증 로직만 임시로 수정하여, vLLM이 띄워진 상태에서 정상 동작하는지 먼저 테스트합니다.
3. **나머지 모듈(Judge, Request, Summarize) 일괄 변경**
   Lite 실험이 vLLM 환경에서 정상적으로 작동함이 확인되면, `open_router_request.py`와 `judge.py`에 동일한 로직을 전파합니다. 파일 이름이 OpenRouter에 종속적인 경우, 이후 리팩토링 과정에서 `llm_inference_client.py` 등으로 이름을 변경하는 것도 고려해 볼 수 있습니다.

---
**비고:** 추가적으로 생성할 `.env` 템플릿 예시는 다음과 같습니다.
```env
# 모델 백엔드가 vLLM일 경우
LLM_API_URL=http://localhost:8000/v1/chat/completions
LLM_API_KEY=dummy_key
EVAL_MODEL_NAME=meta-llama/Meta-Llama-3.1-8B-Instruct
JUDGE_MODEL_NAME=deepseek/deepseek-chat-v3-0324 # 엣지 케이스: Judge마저 로컬 모델을 쓸지, OpenRouter를 쓸지 전략 분리 필요함

사용자 (나)의 검토 : Juge는 openRouter의 DeepSeek R1 $0.55/M input, $2.19/M output을 쓸겁니다. 그냥 vllm은 meta-llama/Meta-Llama-3.1-8B-Instruct만 쓰면 됨.
```
