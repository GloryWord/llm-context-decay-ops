# Worker-3 clean N=83 replay metadata summary

Generated: 2026-05-18T10:24:39Z

## Scope correction

This artifact uses **only** the leader-confirmed isolated clean replay outdir:

`.tmp/q1_finish_reason_rerun/clean_n83_20260518T191600+0900`

The earlier shared default output path is intentionally ignored because leader reported concurrent-writer corruption risk. This artifact does not modify files inside the clean outdir; it only reads them and updates this worker summary file.

## Sources read

- `.tmp/q1_finish_reason_rerun/clean_n83_20260518T191600+0900/manifest_r07_false_truncation_suspect.json` — selector manifest: `target_count=83`, `model=hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4`, `max_tokens=512`, `api_url=http://210.179.28.26:18000/v1/chat/completions`, `dry_run=False`.
- `.tmp/q1_finish_reason_rerun/clean_n83_20260518T191600+0900/replay_metadata_r07_false_truncation_suspect.jsonl` — clean N=83 replay rows; SHA256 `b4a64a114985f7c33c11151edc71f2543f5f405db032d832b142c13121b807f6`.
- `.tmp/q1_finish_reason_rerun/clean_n83_20260518T191600+0900/summary_r07_false_truncation_suspect.json` — clean script summary; SHA256 `a10dde2fcac73e2a1581e3217f083a3dcb87a57629d1ccebe2f9b9054c988d3f`.
- `.tmp/q1_finish_reason_rerun/clean_n83_20260518T191600+0900/replay_run_clean_n83.log` — clean replay execution log.


## Verification command

The correction was validated from the clean outdir only with a Python assertion check equivalent to:

```bash
python3 - <<'PY'
import json, pathlib, collections
clean = pathlib.Path('.tmp/q1_finish_reason_rerun/clean_n83_20260518T191600+0900')
rows = [json.loads(line) for line in (clean / 'replay_metadata_r07_false_truncation_suspect.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(rows) == 83
assert collections.Counter(r.get('ok') for r in rows) == collections.Counter({True: 83})
assert collections.Counter(r.get('finish_reason') for r in rows) == collections.Counter({'length': 79, 'stop': 4})
assert sum(1 for r in rows if (r.get('usage') or {}).get('completion_tokens') == 512) == 79
q = [r for r in rows if r.get('case_id') == 'q1samp_00020' and r.get('turn') == 15]
assert len(q) == 1 and q[0].get('finish_reason') == 'length'
assert (q[0].get('usage') or {}).get('completion_tokens') == 512
assert q[0].get('response_equals_original') is True
PY
```

## Completion / coverage check

- JSONL raw lines: **83**.
- Bad JSON lines: **0**.
- Parsed JSONL rows: **83**.
- Manifest target count: **83**.
- Script summary target count: **83**.
- OK/error counts from rows: `ok=True` **83**, `ok=False` **0**.
- Script summary OK/error: `ok_count=83`, `error_count=0`.
- Returned model distribution: 'hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4'=83.
- Per-row configured `max_tokens`: 512=83.

## Finish reason counts

| finish_reason | count |
| --- | ---: |
| length | 79 |
| stop | 4 |

Script summary finish_reason_counts: `{'length': 79, 'stop': 4}`.

## `usage.completion_tokens == 512`

- Rows with `usage.completion_tokens == 512`: **79 / 83**.
- Rows with `finish_reason == length`: **79 / 83**.
- Script `hit_max_tokens_count`: **79**.
- Completion token distribution: 418=1, 426=1, 432=1, 442=1, 512=79.

Rows not equal to 512 are exactly the `stop` rows:

| index | case_id | turn | finish_reason | completion_tokens | response_equals_original | r07_detail |
| ---: | --- | ---: | --- | ---: | --- | --- |
| 29 | q1samp_00197 | 14 | stop | 432 | False | 요청한 전체 형태를 제공하지 않고 중간에 끊김 |
| 39 | q1samp_00232 | 1 | stop | 418 | False | 요청한 전체 인물 목록을 요약 및 부분본으로 제공함 |
| 60 | q1samp_00307 | 15 | stop | 426 | True | 요청한 전체 인물을 요약 및 생략하여 제공함 |
| 68 | q1samp_00320 | 1 | stop | 442 | False | 요청한 전체 목록 대신 일부만 제공함 |

## `response_equals_original` distribution

| response_equals_original | count |
| --- | ---: |
| False | 17 |
| True | 66 |

Cross-tab by finish_reason:

| finish_reason | response_equals_original | count |
| --- | --- | ---: |
| length | False | 14 |
| length | True | 65 |
| stop | False | 3 |
| stop | True | 1 |

## q1samp_00020 turn15 metadata from the clean N=83 replay

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
  "elapsed_s": 6.846,
  "raw_response_id": "chatcmpl-5d8c4d1e864849349c0ae068dbd40d11",
  "raw_created": 1779099391,
  "messages_sha256": "807511ffb481f5500f020a79069ece222603556d243a552595a06d762ec3f821",
  "system_prompt_sha256": "92278453c48e9c9947eec1761b4de94d1c760ad02f92007633b74db2c882b1a6",
  "r07_detail": "요청한 전체 형태를 제공하지 않고 중간에 끊김",
  "original_response_tail": "님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고, 이스라엘의 조상이 됩니다.\n7. **모세**: 이스라엘의 첫 번째 선지자로, 이스라엘을 이집트에서 해방시키는 역할을 맡았습니다. 그는 하나님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고, 이스라엘을 이집트에서 해방시키는 역할을 맡았습니다.\n8. **다윗**: 이스라엘의 왕으로, 하나님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고,",
  "replay_response_tail": "님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고, 이스라엘의 조상이 됩니다.\n7. **모세**: 이스라엘의 첫 번째 선지자로, 이스라엘을 이집트에서 해방시키는 역할을 맡았습니다. 그는 하나님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고, 이스라엘을 이집트에서 해방시키는 역할을 맡았습니다.\n8. **다윗**: 이스라엘의 왕으로, 하나님의 약속을 받은 인물로 등장합니다. 그는 하나님의 명령을 받고,"
}
```

## Interpretation note

For the clean N=83 targeted rerun, the replay metadata separates generation-limit truncation from normal model stop: **79** rows ended with `finish_reason=length` and `usage.completion_tokens=512`, matching configured `max_tokens=512`; **4** rows ended with `finish_reason=stop` and completion tokens below 512.
