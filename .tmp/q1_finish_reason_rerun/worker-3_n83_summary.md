# Worker-3 N=83 replay metadata summary

Generated: 2026-05-18T10:16:44Z

## Sources read

- `.tmp/q1_finish_reason_rerun/manifest_r07_false_truncation_suspect.json` — selector manifest: `target_count=83`, `model=hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4`, `max_tokens=512`, `api_url=http://210.179.28.26:18000/v1/chat/completions`, `dry_run=False`.
- `.tmp/q1_finish_reason_rerun/replay_metadata_r07_false_truncation_suspect.jsonl` — N=83 replay rows; SHA256 `573300b748942c5ef3a8258732007d0e17b4904be8dc776660f8d9c9402621c9`.
- `.tmp/q1_finish_reason_rerun/summary_r07_false_truncation_suspect.json` — script summary; SHA256 `06af50c84bf27a5e8a79f996f832800bdc249ca2d9adc7bbab3f70781584b67f`.
- `.tmp/q1_finish_reason_rerun/replay_metadata_q1samp_00020_turn15.jsonl` — separate q1samp_00020 proof output exists for single-turn coverage.

## Completion / coverage check

- JSONL row count: **83**.
- Manifest target count: **83**.
- Script summary target count: **83**.
- OK/error counts from rows: `ok=True` **83**, `ok=False` **0**.
- Script summary OK/error: `ok_count=83`, `error_count=0`.
- Returned model distribution: 'hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4'=83.
- Per-row configured `max_tokens`: 512=83.

## Finish reason counts

| finish_reason | count |
| --- | ---: |
| length | 80 |
| stop | 3 |

Script summary finish_reason_counts: `{'length': 80, 'stop': 3}`.

## `usage.completion_tokens == 512`

- Rows with `usage.completion_tokens == 512`: **80 / 83**.
- Rows with `finish_reason == length`: **80 / 83**.
- Script `hit_max_tokens_count`: **80**.
- Completion token distribution: 418=1, 426=1, 442=1, 512=80.

Rows not equal to 512 are exactly the `stop` rows:

| index | case_id | turn | finish_reason | completion_tokens | response_equals_original | r07_detail |
| ---: | --- | ---: | --- | ---: | --- | --- |
| 39 | q1samp_00232 | 1 | stop | 418 | False | 요청한 전체 인물 목록을 요약 및 부분본으로 제공함 |
| 60 | q1samp_00307 | 15 | stop | 426 | True | 요청한 전체 인물을 요약 및 생략하여 제공함 |
| 68 | q1samp_00320 | 1 | stop | 442 | False | 요청한 전체 목록 대신 일부만 제공함 |

## `response_equals_original` distribution

| response_equals_original | count |
| --- | ---: |
| False | 18 |
| True | 65 |

Cross-tab by finish_reason:

| finish_reason | response_equals_original | count |
| --- | --- | ---: |
| length | False | 16 |
| length | True | 64 |
| stop | False | 2 |
| stop | True | 1 |

## q1samp_00020 turn15 metadata from the N=83 replay

```json
{
  "index": 7,
  "case_id": "q1samp_00020",
  "turn": 15,
  "ok": true,
  "finish_reason": "length",
  "usage": {
    "prompt_tokens": 7572,
    "total_tokens": 8084,
    "completion_tokens": 512,
    "prompt_tokens_details": null
  },
  "max_tokens": 512,
  "model_requested": "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4",
  "model_returned": "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4",
  "response_equals_original": true,
  "response_length": 868,
  "original_response_length": 868,
  "prior_turns_from_saved_result": 14,
  "elapsed_s": 7.195,
  "raw_response_id": "chatcmpl-d41d7d32e03c4a299333d10a32b6efd6",
  "raw_created": 1779098876,
  "messages_sha256": "807511ffb481f5500f020a79069ece222603556d243a552595a06d762ec3f821",
  "system_prompt_sha256": "92278453c48e9c9947eec1761b4de94d1c760ad02f92007633b74db2c882b1a6",
  "r07_detail": "요청한 전체 형태를 제공하지 않고 중간에 끊김",
  "original_response_tail": "님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고, 이스라엘의 조상이 됩니다.\n7. **모세**: 이스라엘의 첫 번째 선지자로, 이스라엘을 이집트에서 해방시키는 역할을 맡았습니다. 그는 하나님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고, 이스라엘을 이집트에서 해방시키는 역할을 맡았습니다.\n8. **다윗**: 이스라엘의 왕으로, 하나님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고,",
  "replay_response_tail": "님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고, 이스라엘의 조상이 됩니다.\n7. **모세**: 이스라엘의 첫 번째 선지자로, 이스라엘을 이집트에서 해방시키는 역할을 맡았습니다. 그는 하나님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고, 이스라엘을 이집트에서 해방시키는 역할을 맡았습니다.\n8. **다윗**: 이스라엘의 왕으로, 하나님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고,"
}
```

## Interpretation note

For this N=83 targeted rerun, the replay metadata distinguishes hard generation-limit truncation from normal model stop: 80 rows ended with `finish_reason=length` and `usage.completion_tokens=512`, matching the configured `max_tokens=512`; 3 rows ended with `finish_reason=stop` and completion tokens below 512.
