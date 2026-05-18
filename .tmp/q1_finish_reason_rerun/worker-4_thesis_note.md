# Q1 R07 표적 재실행: max_tokens 절단 판정 근거 노트

- 작성 목적: `r07_false_truncation_suspect` 표적 재실행(N=83)에서 R07 실패가 모델의 자발적 종료인지, 또는 출력 상한(`max_tokens`)에 의한 절단인지 구분하는 논문용 근거를 정리한다.
- 재실행 대상: 원격 vLLM OpenAI 호환 엔드포인트 `http://210.179.28.26:18000/v1/chat/completions`의 `hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4`.
- 핵심 판정 규칙: `finish_reason == "length"`이면서 `usage.completion_tokens == max_tokens == 512`이면 API가 설정된 출력 토큰 상한에 도달해 생성을 중단한 사례로 본다. 반대로 `finish_reason == "stop"`이고 `usage.completion_tokens < max_tokens`이면 출력 상한에 닿지 않고 모델/서빙 계층의 정상 종료 조건으로 멈춘 사례로 본다.

## 1. 재실행 설계와 명령 근거

이번 재실행의 목표는 단순히 기존 응답 텍스트의 꼬리를 보고 “끊겼다”고 판단하는 것이 아니라, vLLM 응답 메타데이터를 함께 저장해 절단 원인을 식별하는 것이다. 작업 컨텍스트는 표적 범위를 `r07_false_truncation_suspect`, 기대 표본 수를 N=83으로 고정하고, 출력 파일이 `finish_reason`, `usage.completion_tokens`, `max_tokens=512`, 반환 모델명, 응답 꼬리와 원본 꼬리를 포함해야 한다고 명시한다(`.omx/context/q1-targeted-rerun-remote-20260518T100319Z.md:6-10`). 같은 문서는 실제 실행 명령도 `VLLM_API_URL=... EVAL_MODEL_NAME=... python3 .tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py --selector r07_false_truncation_suspect`로 기록한다(`.omx/context/q1-targeted-rerun-remote-20260518T100319Z.md:24-34`).

원격 모델 전환 절차는 기존 오케스트레이션 스크립트의 Docker 전환 명령에 근거한다. Llama 대상 컨테이너 전환은 `docker stop vllm-gemma` 후 `docker start vllm-server`를 수행하도록 되어 있으며(`.tmp/run_q1_sampled_llama_then_gemma.sh:177-179`), 이후 Gemma judge 컨테이너로 되돌리는 절차도 별도로 정의되어 있다(`.tmp/run_q1_sampled_llama_then_gemma.sh:195-197`). 따라서 이번 표적 재실행은 Gemma judge가 아니라 Llama 대상 모델에서 생성 메타데이터를 확보하는 절차로 해석해야 한다.

## 2. 메타데이터 수집 방식

재실행 스크립트는 기본 API URL과 모델명을 원격 Llama vLLM 엔드포인트로 둔다(`.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:30-31`). 인자는 `--max-tokens` 기본값을 512로 정의한다(`.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:162-167`). 실제 요청 payload에는 `model`, `messages`, `temperature`, `max_tokens`가 포함된다(`.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:207-212`). 응답을 받은 뒤 각 행에는 `max_tokens`, `finish_reason`, `usage`, `model_returned`, `response_equals_original`, 원본/재실행 응답 꼬리가 저장된다(`.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:218-235`).

또한 스크립트는 실행 종료 시 `target_count`, `ok_count`, `error_count`, `finish_reason_counts`, `hit_max_tokens_count`를 요약 파일로 저장한다(`.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:265-282`). 이 때문에 본 노트의 판정은 응답 텍스트만의 주관적 판단이 아니라, API가 반환한 종료 사유와 토큰 사용량의 결합 조건에 근거한다.

## 3. N=83 재실행 결과 요약

완료된 요약 파일 `.tmp/q1_finish_reason_rerun/summary_r07_false_truncation_suspect.json`은 다음을 기록한다.

| 항목 | 값 |
|---|---:|
| selector | `r07_false_truncation_suspect` |
| target_count | 83 |
| ok_count | 83 |
| error_count | 0 |
| finish_reason=`length` | 80 |
| finish_reason=`stop` | 3 |
| hit_max_tokens_count | 80 |

동일한 값은 실행 로그 `.tmp/q1_finish_reason_rerun/replay_run_r07_false_truncation_suspect_20260518T191000+0900.log` 말미의 JSON 요약에도 기록되어 있다. 즉, 표적 83건은 모두 API 호출에 성공했고, 그중 80건은 출력 상한에 도달한 것으로 집계되었다. 원자료 `.tmp/q1_finish_reason_rerun/replay_metadata_r07_false_truncation_suspect.jsonl`을 재계산하면 `max_tokens=512`가 83건 모두에 적용되었고, 반환 모델명도 83건 모두 `hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4`였다.

## 4. 절단 판정 규칙과 해석

본 실험에서 “max_tokens 절단”으로 분류하는 충분조건은 다음과 같다.

1. 요청 설정의 `max_tokens`가 512로 고정되어 있다.
2. API 응답의 `finish_reason`이 `length`이다.
3. API 응답의 `usage.completion_tokens`가 512로, 요청 상한과 정확히 일치한다.

이 세 조건이 동시에 성립하면, 모델이 의미상 답변을 완성해서 멈춘 것이 아니라 서빙 API가 허용된 출력 토큰 수를 모두 사용했기 때문에 생성을 종료한 것으로 해석한다. 이번 N=83 재실행에서는 이 조건이 80건에서 성립했다. 따라서 `r07_false_truncation_suspect` 표본의 대부분은 “응답 내용이 끝까지 도달하지 못했다”는 관찰과 메타데이터상 출력 상한 도달이 일치한다.

반대로 `finish_reason=stop`인 3건은 각각 `completion_tokens`가 418, 426, 442로 모두 512보다 작았다. 이 경우는 출력 상한에 닿지 않았으므로 max_tokens 절단으로 분류하지 않는다. 이 3건은 모델이 정지 토큰 또는 자체 종료 조건으로 멈춘 사례이며, R07 실패 여부는 별도로 내용 완결성 기준에서 판단해야 한다.

## 5. q1samp_00020 사례

논문 서술에서 대표 사례로 사용할 수 있는 `q1samp_00020`은 N=83 JSONL의 7번째 행에 포함되어 있다(`.tmp/q1_finish_reason_rerun/replay_metadata_r07_false_truncation_suspect.jsonl:7`). 해당 행은 `case_id=q1samp_00020`, `turn=15`, `finish_reason="length"`, `usage.completion_tokens=512`, `max_tokens=512`, `model_returned="hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"`, `response_equals_original=true`를 기록한다. 응답 꼬리는 “8. **다윗** ... 그는 하나님의 명령을 받고,”에서 끝나므로, 텍스트상 미완결 꼬리와 메타데이터상 출력 상한 도달이 함께 관측된다.

이 사례는 “원문과 재실행 응답이 동일해서 재현성이 확보된 상태에서, finish_reason과 completion_tokens가 절단 원인을 직접 설명한다”는 점에서 thesis-ready 예시로 적합하다. 즉, q1samp_00020 turn 15는 단순한 휴리스틱이 아니라 `finish_reason=length ∧ completion_tokens=max_tokens=512` 조건으로 출력 상한 절단을 식별할 수 있는 대표 근거이다.

## 6. 논문 본문용 요약 문장

> R07 실패 후보 83개 turn을 동일한 Llama vLLM 엔드포인트에서 재실행하고 OpenAI 호환 응답 메타데이터를 저장한 결과, 80건은 `finish_reason=length`이면서 `usage.completion_tokens`가 설정 상한인 `max_tokens=512`에 정확히 도달했다. 따라서 이 80건은 모델이 의미적으로 답변을 완료한 뒤 멈춘 사례가 아니라, 출력 토큰 예산에 의해 응답이 절단된 사례로 해석했다. 반면 3건은 `finish_reason=stop`이고 completion token 수가 512 미만이어서 max_tokens 절단이 아닌 모델/서빙 계층의 정상 종료 사례로 분리했다.

## 7. 근거 파일 목록

- 실행 컨텍스트와 명령: `.omx/context/q1-targeted-rerun-remote-20260518T100319Z.md:6-10`, `.omx/context/q1-targeted-rerun-remote-20260518T100319Z.md:24-34`
- 원격 Llama 컨테이너 전환 근거: `.tmp/run_q1_sampled_llama_then_gemma.sh:177-179`
- 재실행 스크립트의 기본 URL/모델/토큰 상한: `.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:30-31`, `.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:162-167`
- payload 및 저장 필드: `.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:207-235`
- summary 생성 로직: `.tmp/q1_finish_reason_rerun/replay_q1_turns_with_metadata.py:265-282`
- N=83 요약: `.tmp/q1_finish_reason_rerun/summary_r07_false_truncation_suspect.json`
- 원자료 JSONL: `.tmp/q1_finish_reason_rerun/replay_metadata_r07_false_truncation_suspect.jsonl`
- 완료 로그: `.tmp/q1_finish_reason_rerun/replay_run_r07_false_truncation_suspect_20260518T191000+0900.log`
