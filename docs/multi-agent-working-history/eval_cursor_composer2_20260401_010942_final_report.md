# Cursor Agent Evaluation — composer2

- **Date**: 2026-04-01 01:10
- **Deliverable**: docs/outputs/final_report.md
- **Model**: composer-2
- **Role**: composer2

## Result


저장소에는 `data/outputs/main_experiment/*.jsonl`·`docs/outputs/experiment_summary.json`이 없어(대개 gitignore 또는 미커밋) 보고서 표의 **원시 수치와의 1:1 대조**는 이 환경에서 수행하지 못했습니다. 대신 `scripts/generate_report.py`의 `compute_summary()`·임계값 정의와 작업 기록(`docs/multi-agent-working-history/2026-03-31_2220_experiment-complete-single-model.md`)을 코드·문서와 교차해 검토했습니다.

---

## 검증 요약

| 항목 | 등급 | 한줄 근거 |
|------|------|-----------|
| (1) 데이터 정합성 | **중** | 집계 키·임계 알고리즘은 코드와 정합; 원시 JSON 부재로 표 수치·29,700/10,890 건수는 **직접 검증 불가**. 사내 기록과 임계턴(T3.3 vs T4.2 등) **버전 차이** 존재. |
| (2) 코드 구조 | **상** | `generate_full_cases` → `run_experiment_fast`(추론·자동채점) → 배치 judge → `generate_report`로 역할 분리가 분명하고, `compliance_scorer` 레지스트리 패턴이 적절함. |
| (3) 파이프라인 일관성 | **중** | end-to-end 흐름은 일치하나 `compliance_scorer.py` 주석·기본 `JUDGE_MODEL`은 **R1**이고 보고서는 **DeepSeek V3** — 실행 환경(`JUDGE_MODEL_NAME`)과 문서를 맞출 필요가 있음. |
| (4) 논리적 일관성 | **중** | 가설·표·시각화 해석은 대체로 연결됨. 다만 **Lost in the Middle**는 시스템 프롬프트 준수와 직접 동일 문제는 아니어서 비유가 약함; R5·R7에서 **benign &lt; adversarial** 구간은 분산·포맷 베이스라인으로 읽을 수 있으나 보고서에서 **우연/분산** 가능성을 더 분명히 할 여지가 있음. |
| (5) 코드 품질 | **중** | `temperature=0`, API 재시도 등 재현에 유리; **시드 고정**은 vLLM/API에 명시적으로 묶여 있지 않음. 타입 힌트·`tests/test_compliance_scorer.py`는 일부. 배치 judge에서 **규칙·점수 인덱스 정렬** 가정은 데이터가 어긋나면 위험(구조상 주의점). |
| (6) 개선 제안 | **상** | 아래 제안은 구체적으로 실행 가능하고, 범위도 명확함. |

---

## (1) 데이터 정합성 — **중**

- **일치하는 점**: §3.1 형식은 `compute_summary()`의 `condition_stats`와 같이 `(rule_count, turn_count, attack)` 셀마다 **마지막 턴 준수율**을 모아 평균하는 구조와 맞습니다. §3.2 DO/CT는 각 run에서 **첫** `compliance_rate < 0.8` / `< 0.5` 턴을 찾은 뒤 `R{rc}_{attack}`별로 평균·`n`을 내는 방식과 동일합니다 (`generate_report.py` 257–293행 근처).
- **검증 한계**: 308×5·10,890 응답·87분 등은 설계상 타당하나, **29,700** 자동 검사는 레포에 동일 산식이 없고, 턴마다 적용 규칙 수·N/A가 달라 단순 곱으로는 재현 확인이 어렵습니다.
- **문서 간 불일치**: 동일 실험에 대한 작업 기록의 R1 adversarial DO가 **T3.3**인데, 제시 보고서는 **T4.2** — judge 반영 후 재생성으로 설명 가능하지만, 외부 검증자는 **어느 버전이 최종인지** 메타데이터가 필요합니다.

---

## (2) 코드 구조 — **상**

- `scripts/`(실험·보고서)와 `src/evaluation/`(채점) 분리, `lite_experiment` vs `run_experiment_fast` 역할 구분이 읽기 쉽습니다.
- 중복은 `run_experiment.py`와 `run_experiment_fast.py` 사이에 일부 있으나, “전체 judge 내장” vs “배치 judge”라는 **의도적 분기**로 보입니다.

---

## (3) 파이프라인 일관성 — **중**

- 케이스 생성 → 추론 → 자동채점 → (배치) judge → 요약·그림은 README/스크립트와 맞습니다.
- **보고서와 코드 기본값 불일치**: judge 모델명을 README·`compliance_scorer` 상단·실행 로그에 **한 줄로 고정**하지 않으면 재현 시 판정이 달라질 수 있습니다.

---

## (4) 논리적 일관성 — **중**

- H1 “부분 지지”, H2 “공격 있을 때만 감쇠”, H3 “강하게 지지”는 표와 방향이 대체로 맞습니다.
- **과대 해석 가능 구간**: (i) **Attention 비중·Distraction**은 측정 없이 메커니즘 설명으로 쓰이면 추측에 가깝습니다. (ii) **Lost in the Middle**는 본질적으로 retrieval/위치 효과 논의라, “benign에서 턴 증가 시 SP 준수 유지”와의 대조는 가능하나 **동일 이론의 직접 반증**으로 쓰기엔 범주가 다릅니다.

---

## (5) 코드 품질 — **중**

- **장점**: `temperature=0`, HTTP 재시도, 출력 디렉터리 고정.
- **아쉬운 점**: 전역 RNG/시드, vLLM `seed` 파라미터 명시, 실험 설정 해시를 JSON에 기록하는 부분이 약함. 단위 테스트는 채점 모듈 위주.

---

## (6) 개선 제안 — **상** (구체안)

1. **재현성**: 결과 JSONL에 `judge_model`, `target_model`, `temperature`, `cases_file` 해시, `generate_report.py` git commit 해시를 한 블록으로 기록.
2. **정합 검증 스크립트**: `results_*.jsonl`만 있으면 §3.1·§3.2·총 턴 수·자동 rule 검사 횟수를 재계산하는 `scripts/verify_report_numbers.py` 추가.
3. **통계**: 셀별 **95% CI** 또는 **부트스트랩**으로 R5/R7의 “역전된 갭”이 0을 포함하는지 표시.
4. **문헌 비교**: Lost in the Middle 대신 **multi-turn instruction following** 또는 **jailbreak 점진 공격** 쪽 문헌으로 토론 각주를 맞추면 논리 긴장이 줄어듦.
5. **테스트**: `generate_report.compute_summary`에 고정 소표 JSON 픽스처로 스냅샷 테스트.
6. **Judge 안전성**: 배치 judge에서 `rule_id`로 규칙을 매칭해 점수에 붙이고, 인덱스 가정 제거.

---

### 종합

보고서는 **파이프라인·집계 정의와 잘 맞물리도록 작성된 편**이나, 이 검증 세션에서는 **원시 결과 파일 없이 수치·건수를 끝까지 입증하진 못했고**, 문서 간 임계값 차이와 **judge 모델 문서화**는 정리할 가치가 있습니다. 전체적으로 **방법·구조는 상·중상**, **검증 가능한 수치 서술·외부 문헌 대응은 중** 정도로 보는 것이 타당합니다.

---

**Codex High 최종 검증(`--final`)을 실행할까요?** (프로젝트 규칙상 완료 후 확인 질문입니다.)
