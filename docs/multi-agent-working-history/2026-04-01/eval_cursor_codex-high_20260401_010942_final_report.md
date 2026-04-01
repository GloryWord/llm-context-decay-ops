# Cursor Agent Evaluation — codex-high

- **Date**: 2026-04-01 01:21
- **Deliverable**: docs/outputs/final_report.md
- **Model**: gpt-5.3-codex-high
- **Role**: codex-high

## Result

## 최종 판정: **FAIL**

최종 배포 전 감사 기준으로는 통과할 수 없습니다.  
핵심 이유는 **수치 정의 불일치(필수 지표 오류)**, **통계 해석 과대 주장**, **클린 재실행 리스크(의존성/예외처리/스키마 불일치)** 입니다.

## 기준별 결과

- **(1) 수치 완전 검증**: **FAIL**
  - 원본 `fast_results_*.jsonl` 기준 `runs=1540`, `cases=308`, `responses=10890`는 일치.
  - 3.1/3.2 표 수치는 `experiment_summary.json`과 일치.
  - 그러나 보고서의 `Auto-scoring 29,700` / `LLM-judge 10,890`는 **rule-evaluation 기준과 불일치**.  
    (케이스 설계와 스코어 구조 기준으로는 `auto=33,660`, `judge=6,930`이 맞음)
- **(2) 논문 수준 엄밀성**: **FAIL**
  - “decay는 공격에 의해서만 발생” 같은 문장이 표/임계치와 충돌.
  - SD 해석(“반복 간 변동”)이 실제 집계 단위(케이스+반복 혼합)와 다름.
  - `temperature=0`에서 같은 케이스 반복이 동일 출력인 사례가 있어 독립 표본 해석에 문제.
- **(3) 코드 프로덕션 준비(클린 재실행)**: **FAIL**
  - `requirements.txt`에 실제 사용 의존성(`python-dotenv`, `langdetect`) 누락.
  - `run_experiment_fast.py`에서 예외를 삼켜 데이터 무결성 위험.
  - `generate_report.py` 기본 입력 패턴이 `results_*.jsonl`이라 실험 주 산출물(`fast_results_*.jsonl`)과 어긋날 수 있음.
- **(4) 아키텍처 최종 검토**: **FAIL**
  - vLLM 공인 IP 기본값 하드코딩.
  - 중복된 러너/호출 로직 다수, 설정 드리프트 위험.
  - 리포트 코드가 결과 스키마(`rules` 필드 유무)에 의존하여 러너별 비일관성 발생 가능.
- **(5) 발표/제출 준비**: **FAIL**
  - 본문 서술과 표/그래프 간 모순 존재(예: R5/R7 초기 gap 음수인데 “항상 adversarial이 더 낮다” 서술).

## 수정 필수 항목 (반드시 반영)

1. **지표 정의 정정(최우선)**  
   - `29,700`/`10,890`를 무엇의 카운트인지 명확히 재정의하고, 실제 계산식과 일치시키세요.  
   - 권장: `response-level`, `rule-evaluation-level` 지표를 분리 표기.
2. **리포트-코드-로그 일치성 확보**  
   - 결과 JSON에 `judge_model`, `judge_version`, `scoring_schema_version` 필드를 저장.  
   - 보고서의 “DeepSeek V3” 문구를 실행 로그 근거 기반으로 자동 생성.
3. **통계 서술 수정**  
   - “강하게 지지”, “공격에 의해서만 발생” 등 과대 문구를 완화하거나 통계검정 근거 추가.  
   - SD/SEM/CI 용어를 정확히 구분하고 캡션에 집계 단위 명시.
4. **Q2 시각화 로직 수정**  
   - rule type 그래프를 benign/adversarial 분리 집계로 변경.  
   - 결과 스키마에 `rules`가 없어도 동작하도록 `rule_id -> type` 매핑 고정 테이블 도입.
5. **클린 재실행 보장**  
   - `requirements.txt`에 `python-dotenv`, `langdetect`(및 테스트 실행시 `pytest`) 추가.  
   - `generate_report.py` 기본 입력을 실제 운영 파일 패턴과 맞추기.
6. **실패 은닉 제거**  
   - `run_experiment_fast.py`의 `return_exceptions=True` 후 무검사 로직 제거, 실패 시 종료코드 비정상 처리.
7. **보안/운영 설정 정리**  
   - 공인 IP 기본값 제거, 환경변수 필수화(미설정 시 명확한 에러).
8. **본문-표-그래프 정합성 교정**  
   - R5/R7 초기 구간, language 추세, benign threshold 문장 등 모순 문구 정정.

## 근거 코드/문서 발췌

```100:137:scripts/generate_report.py
for r in records:
    for t in r["turn_results"]:
        for s in t["scores"]:
            if s["pass"] is not None:
                rtype = _get_rule_type(s["rule_id"], r.get("rules", []))
                type_turns[rtype][t["turn"]].append(1.0 if s["pass"] else 0.0)

def _get_rule_type(rule_id: str, rules: list[dict]) -> str:
    for r in rules:
        if r.get("rule_id") == rule_id:
            return r.get("type", "unknown")
    return "unknown"
```

```221:232:scripts/run_experiment.py
return {
    "case_id": case_id,
    "rep": rep,
    "model": model_name,
    "research_question": case.get("research_question", ""),
    "rule_count": case["rule_count"],
    "turn_count": case["turn_count"],
    "attack_intensity": case["attack_intensity"],
    "rule_set_variant": case.get("rule_set_variant", []),
    "turn_results": turn_results,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
}
```

```229:230:scripts/run_experiment_fast.py
tasks = [bounded_run(c, r) for c, r in work]
await asyncio.gather(*tasks, return_exceptions=True)
```

```159:179:docs/outputs/final_report.md
| 5 | 1 | 81.2% | 83.3% | -2.1pp |
| 7 | 1 | 77.5% | 81.2% | -3.7pp |
...
| R3 benign | T1.1 (format baseline) | — |
| R5 benign | T1.1 (format baseline) | T3.0 (rare, n=20) |
| R7 benign | T3.0 (rare, n=33) | T13.0 (very rare, n=3) |
```

원하시면 다음 단계로, 위 8개 항목을 기준으로 **수정 우선순위(1일/3일/1주)**까지 바로 실행 계획 형태로 정리해드리겠습니다.
