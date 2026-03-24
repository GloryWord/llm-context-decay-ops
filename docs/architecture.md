# System Architecture (v2)

> Not auto-loaded. Reference explicitly when needed.
> Updated: 2026-03-24

## Pipeline

```
Phase 1 v2 (현재):
  [data/raw/]
      │
      ▼
  [src/data_pipeline/] — download, preprocess, probe generation
      │  generate_multi_rule_probes.py → aegis_probes.jsonl
      │  generate_experiment_cases.py  → experiment_cases.jsonl
      ▼
  [data/processed/experiment_cases.jsonl]
      │
      ▼
  [src/models/open_router_request.py]
      │  OpenRouter API (Qwen3.5-9B, reasoning off)
      ▼
  [data/outputs/{model}/{variant}/results.jsonl]
      │
      ▼
  [Project Aegis score_rule() + evaluation.py]
      │  per-rule compliance scoring
      ▼
  [reports/evaluation_summary.json + scored_results.jsonl]
      │
      ▼
  [reports/figures/*.png + reports/phase1_report.md]
```

## Config Structure

```
configs/
├── preprocess.yaml   ← Phase 1 preprocessing + experiment design params
└── compression.yaml  ← Phase 2 compression params (보류)
```

## Environment Variables

```bash
OPENROUTER_API_KEY=<your_key>
```

## Key Design Decisions (v2)

- **Single user message embedding:** Chat Template 호환을 위해 user_only 턴을 단일 메시지에 임베딩
- **Qwen BPE tokenizer:** tiktoken → transformers AutoTokenizer (Qwen/Qwen3.5-9B)
- **Project Aegis:** 도메인 응집형 20-rule persona, regex/string 기반 자동 채점
- **Reasoning off:** `reasoning: {"effort": "none"}` — 비용/시간 절감
