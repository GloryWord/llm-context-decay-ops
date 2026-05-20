# NoonAI DIS MCP Server - AI 에이전트 팀 구축 플랜

이 문서는 `/Users/kawai_tofu/MHNCity/MCP_for_DIS/noonai-dis-mcp-server` 프로젝트에 적용할 Multi-Agent 기반 작업/평가 워크플로우 구축 계획을 담고 있습니다. 기존 실험 저장소의 모델과 유사한 자동화 구조를 가지되, 역할과 책임(R&R)이 새로운 프로젝트 요구 사항에 맞게 변동되었습니다.

---

## 1. 아키텍처 및 역할(R&R) 정의

이 프로젝트에서는 총 3개의 AI 에이전트(모델)가 협업하며, 최종 승인자(Final Approver) 단계를 생략하여 빠르고 민첩한 사이클을 지향합니다.

| 역할 | 에이전트(모델) | 주요 책임 | 비고 |
| :--- | :--- | :--- | :--- |
| **Orchestrator (오케스트레이터)** | **Gemini** | 파이프라인 총괄 관리, 작업 지시 생성, 피드백 정리, 루프 제어 | 유일한 사용자 접점 |
| **Coder (실무 코더)** | **Cursor (composer-2)** | Gemini의 지시를 기반으로 실제 코드 작성, 파일 수정, 기능 구현 | 코드 구조 및 아키텍처 구현 |
| **Evaluator (평가자)** | **MJ_Codex (gpt-5.4)** | 작성된 코드 및 산출물의 논리적 정합성, 요구사항 충족 여부 검토 및 피드백 (PASS/BLOCK 반환) | 코드 리뷰어 역할 |
| **Final Approver (최종 승인자)**| **(없음)** | - | 신속한 개발을 위해 생략 |

### 🔄 데이터 흐름 (Workflow Loop)
1. **[Gemini]** 사용자 요청 분석 및 코딩 지시 패킷 생성 (`task_packet.yaml` 등).
2. **[Cursor]** 패킷을 수신하여 `composer-2`를 통해 코드를 작성.
3. **[MJ_Codex]** 작성된 코드를 스캔 및 테스트하여 `gpt-5.4`를 통해 리뷰 및 평가 (`eval_result.yaml` 생성).
4. **[Gemini]** 평가 결과가 `PASS`이면 다음 태스크로 진행, `BLOCK`이면 피드백을 수렴하여 Cursor에게 재수정 지시. (최대 재시도 루프: 2~3회)

---

## 2. 디렉토리 구조 계획

새 프로젝트 루트(`/Users/kawai_tofu/MHNCity/MCP_for_DIS/noonai-dis-mcp-server`)에 아래와 같은 에이전트 전용 디렉토리 및 스크립트를 구성합니다.

```text
noonai-dis-mcp-server/
├── GEMINI.md                  ← Gemini용 Global Prompt / 규칙 문서 (오케스트레이터 룰셋)
├── docs/
│   ├── acpx_prompts/          ← Cursor 및 MJ_Codex용 시스템 프롬프트
│   └── agent-work-history/    ← 에이전트별 작업 내용 및 평가 결과 로깅 (YYYY-MM-DD/ 폴더별 로깅)
└── scripts/
    └── agent_workflow/
        ├── eval_loop.sh       ← 전체 평가 워크플로우 실행 진입점
        ├── run_coder.sh       ← Cursor(composer-2) acpx 호출 래퍼
        └── run_evaluator.sh   ← MJ_Codex(gpt-5.4) acpx 호출 래퍼
```

---

## 3. 단계별 구축 플랜

### Step 1: 프로젝트 기초 환경 셋업
- `/Users/kawai_tofu/MHNCity/MCP_for_DIS/noonai-dis-mcp-server` 경로 생성 및 Git 초기화.
- `.gitignore` 설정 (로깅 폴더 등 무거운 자산 제외 가능하도록).

### Step 2: 오케스트레이터 규칙(GEMINI.md) 작성
- 프롬프트 엔지니어링 수행.
- Gemini가 오케스트레이터로서 어떻게 Cursor를 호출하고, MJ_Codex의 피드백을 수렴할 것인지 규칙 명시.
- 평가 스킵 불가, 작업 후 반드시 `eval_loop.sh`를 실행하도록 강력한 지침 포함.

### Step 3: ACPX CLI 연동 스크립트 작성 (`scripts/agent_workflow/`)
- 기존 기존 `scripts/gemini_only/*.sh` 패턴을 참고하되, 역할에 맞추어 스크립트 리팩토링.
- **`run_coder.sh`**: `--model composer-2` 옵션을 강제하여 코딩 스크립트 실행.
- **`run_evaluator.sh`**: `--model mj-codex` (혹은 동료 PC 원격 연결 프로필 지정)로 전달하여 `gpt-5.4`가 코드를 평가하게 함.
- **`eval_loop.sh`**: 위 두 스크립트를 연결하며, 루프 상한선(Max Loops) 도달 시 Gemini에게 제어권 반환하도록 구현.

### Step 4: 작업 기록 로깅 체계 마련
- `docs/agent-work-history/YYYY-MM-DD/HHMMSS_TaskName/` 구조로 로그를 저장하게 쉘 스크립트에 포함.
- `task_packet.yaml`, `coder_diff.diff`, `eval_result.yaml` 의 포맷 통합.

---

## 4. 기존 아키텍처와 비교 (주의사항)

1. **승인자 부재**: '최종 승인' 단계가 생략되었으므로, **MJ_Codex(Evaluator)**의 `PASS`/`BLOCK` 판정 기준을 보다 엄격하고 명확하게 프롬프트(`docs/acpx_prompts/`)에 남겨야 합니다.
2. **무한 루프 방지 지침**: 재수정 시도(MAX LOOPS)는 최대 2회로 제한하고, 연속으로 실패할 경우 오케스트레이터(Gemini)가 반드시 **사용자(인간)의 개입**을 요청하게끔 스크립트를 견고히 짜야 합니다.
3. **MJ_Codex 원격 연결**: 이미 셋업된 동료 PC(210.179.28.26)의 SSH 키 및 `mj-codex` 서비스 권한이 새 프로젝트에서도 문제없이 참조(acpx config) 가능한지 확인해야 합니다.
