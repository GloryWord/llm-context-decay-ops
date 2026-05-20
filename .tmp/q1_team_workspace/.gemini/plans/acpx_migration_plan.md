# AI 상호 평가 Agents (ACPX) 도입 업데이트 플랜

새롭게 추가된 `docs/acpx_prompts` 파일들을 분석한 결과, 기존 `Claude Code + Cursor` 중심의 다중 평가자(Multi-Agent) 아키텍처를 전면 개편해야 합니다. 새로운 시스템인 **ACPX 기반 체계**에서는 `composer-2`를 완전히 배제하고 역할(오케스트레이터, 수정자, 수치 감사자, 최종 검증자)을 엄격히 분리하게 됩니다.

## 1. 개요 및 구조 변경 사항

기존의 `eval_cursor.sh` 기반 `composer-2` 타당성 평가 위주의 로직을 완전히 삭제하고, MJ_Codex 기반의 `Reviser`와 Cursor 기반의 단일 `Final Verifier` 형태로 평가/수정 파이프라인을 교체합니다. 스크립트 실행 구조가 근본적으로 바뀝니다.

## 2. 세부 진행 계획

### 2.1 프로젝트 전역 규칙 (`GEMINI.md`) 수정
기존 `GEMINI.md`에 기재된 Multi-Agent Workflow를 새 ACPX 운영 명세(`ACPX_OPERATING_SPEC.md`)에 맞추어 전면 수정합니다.

- **수정 목표**: 
  - `Multi-Agent Workflow (필수 준수)` 섹션을 새 체계로 업데이트.
  - **오케스트레이터**: Gemini 
  - **수정자 (Reviser)**: MJ_Codex (`MJ/gpt-5.4`)
  - **수치 감사자 (Numeric Auditor)**: MJ_Codex (`MJ/gpt-5.3-codex`, 필요 시)
  - **최종 검증자 (Final Verifier)**: Cursor AI (`Cursor/gpt-5.4-high` 또는 `extra-high`)
  - `composer-2` 사용 일체 금지 명시.
  - 동일한 피드백이 재발생하는 지연을 방지하기 위해 Max loops=2 처리 규칙 구체화.

---

### 2.2 평가 및 실행 파이프라인 스크립트 리팩토링 (`scripts/gemini_only/`)
`ACPX_EXECUTION_TEMPLATES.md`에 명시된 실행 골격(Minimal ACPX Skeleton)을 구현하도록 스크립트들을 리팩토링 및 신설합니다.

#### 1) 기존 `eval_cursor.sh` 파기
- 기존의 Tiered Workflow(1단계 composer2 -> 2단계 mj-codex -> 3단계 gpt) 코드를 완전히 버림.

#### 2) 신규 `acpx_cursor_runner.sh` (Final Verifier 전용) 신설
- 오직 `FINAL_VERIFIER_PROMPT.md` 기반의 `Final Verifier` 역할만 하도록 새롭게 작성.
- 입력으로 `packet.yaml`, `revised.md`, `numeric_audit.yaml`(선택적) 정보 등을 받아 최종 `PASS`/`BLOCK` 결과를 판별하는 `verdict.yaml`을 생성 및 반환.

#### 3) 신규 `acpx_mj_runner.sh` (Reviser / Numeric Auditor 전용) 신설
- 기존 `mj_codex` ssh 원격 실행 로직(eval_cursor.sh에 내장되었던 부분)을 독립된 전용 스크립트로 분리.
- `--model`, `--prompt-file`, `--packet`, `--doc` 인자를 받아 `Reviser` 모델 또는 `Numeric Auditor` 모델들을 분기하여 실행하는 범용 래퍼 역할.

#### 4) 기존 `eval_all.sh` 교체 (루프 컨트롤러)
- 기존의 단순 순차 평가 래퍼에서 벗어나, Route A(일반 수정) / Route B(수치 수정) 분기를 지원하는 핵심 ACPX 루프 컨트롤러 역할로 리팩토링.
- `max_loops = 2` 정책 적용: 첫 번째 검증이 `BLOCK` 시 재수정 루프 1회 추가 로직 제어.

---

## 3. 검증 전략 (Verification Strategy)

- **Automated Tests**: 모의 수정 대상 파일과 피드백 파일을 임시로 마련(Mock-up)하여 `packet.yaml`을 직접 만들어 인가해보고 전체 `eval_all.sh` 루프(`revised.md` → `verdict.yaml` 생성 과정)를 1회 시뮬레이션 합니다.
- **Manual Verification**: 시스템 환경에서 `composer-2` 모델이 어떠한 경로로든 호출되지 않는지(ssh 로그 확인), 그리고 두 번의 `verdict.yaml` 판정이 BLOCK일 시 최종 루프가 정상 종료되는지를 체크합니다.

## 4. 확인 및 승인 요청 (Open Questions)

> 위 플랜으로 진행하기 전 다음 두 가지 항목 확인을 요청합니다.
> 1. `acpx_mj_runner.sh` 구성 시 기존 SSH(`mhncity@210.179.28.26`) 접속 정보를 그대로 유지하여 스크립트를 짜면 될까요? → yes
> 2. `ACPX_EXECUTION_TEMPLATES.md`를 보면 `<gemini-runner>`를 이용하여 첫 `packet.yaml`을 생성합니다. 이것을 파이프라인 전면 스크립트에 통합할지, 아니면 저(Gemini)나 사용자가 수동으로 만들어 `eval_all.sh` 파라미터로 넘겨줄지 결정이 필요합니다. → gemini가 만듦.
