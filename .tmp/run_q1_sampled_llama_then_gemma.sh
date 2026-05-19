#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops"
cd "$ROOT"

CASES_FILE="${CASES_FILE:-$ROOT/data/processed/q1_target_balanced_q2_injection_cases.jsonl}"
TRACE_CSV="${TRACE_CSV:-${CASES_FILE%.jsonl}_trace.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/data/outputs/2026-05-19_q1_target_balanced_local_llama_gemma}"
LOG_DIR="$OUTPUT_DIR/logs"
MANIFEST="$OUTPUT_DIR/run_manifest.json"
TARGET_API_URL="http://210.179.28.26:18000/v1/chat/completions"
MODELS_API_URL="http://210.179.28.26:18000/v1/models"
LLAMA_MODEL="hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
GEMMA_MODEL="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -J mhncity@210.179.28.26)
VLLM_HOST="mhncity@172.30.1.13"
RESULT_JSONL="$OUTPUT_DIR/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl"

mkdir -p "$LOG_DIR"
export ROOT CASES_FILE TRACE_CSV OUTPUT_DIR LOG_DIR MANIFEST RESULT_JSONL TARGET_API_URL MODELS_API_URL LLAMA_MODEL GEMMA_MODEL

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" | tee -a "$LOG_DIR/orchestrator.log"
}

ssh_vllm() {
  ssh "${SSH_OPTS[@]}" "$VLLM_HOST" "$@"
}

wait_for_model() {
  local expected="$1"
  local label="$2"
  local attempts="${3:-180}"
  local sleep_s="${4:-5}"
  log "waiting for $label model endpoint and chat-completion readiness: $expected"
  for i in $(seq 1 "$attempts"); do
    local body
    body=$(curl -sS --connect-timeout 3 --max-time 10 "$MODELS_API_URL" 2>/dev/null || true)
    printf '%s\n' "$body" > "$LOG_DIR/models_${label}_attempt_${i}.json"
    if printf '%s' "$body" | grep -Fq "$expected"; then
      if VLLM_API_URL="$TARGET_API_URL" \
        VLLM_MODELS_URL="$MODELS_API_URL" \
        EVAL_MODEL_NAME="$expected" \
        .venv/bin/python scripts/test_vllm_conn.py \
          --quiet \
          --timeout 30 \
          --max-tokens 8 \
          >"$LOG_DIR/readiness_${label}_attempt_${i}.log" 2>&1; then
        log "$label endpoint and chat completions ready after attempt $i"
        curl -sS --connect-timeout 5 --max-time 20 "$MODELS_API_URL" | tee "$LOG_DIR/models_${label}_ready.json" >/dev/null
        cat "$LOG_DIR/readiness_${label}_attempt_${i}.log" | tee -a "$LOG_DIR/orchestrator.log" >/dev/null
        return 0
      fi
      log "$label model listed but chat completion probe not ready at attempt $i"
      cat "$LOG_DIR/readiness_${label}_attempt_${i}.log" | tee -a "$LOG_DIR/orchestrator.log" >/dev/null
    fi
    if (( i % 12 == 0 )); then
      log "$label wait attempt $i/$attempts still not ready"
      ssh_vllm "docker ps --format '{{.Names}} {{.Status}} {{.Ports}}' | grep -E 'vllm|gemma' || true" | tee -a "$LOG_DIR/orchestrator.log" || true
    fi
    sleep "$sleep_s"
  done
  log "ERROR: $label endpoint did not expose expected model: $expected"
  return 1
}

generate_target_balanced_cases() {
  log "Generating Q1 target-balanced cases for all Q2-available rules (R08 excluded)"
  .venv/bin/python scripts/generate_q1_sampled_cases.py \
    --all-target-rules \
    --output "$CASES_FILE" \
    --trace-csv "$TRACE_CSV" \
    2>&1 | tee "$LOG_DIR/generate_cases.log"
}

write_manifest_pre() {
  python3 - <<'PY'
from pathlib import Path
import json, hashlib, collections, datetime, os, subprocess
root=Path(os.environ['ROOT'])
cases=Path(os.environ['CASES_FILE'])
trace=Path(os.environ['TRACE_CSV'])
out=Path(os.environ['MANIFEST'])
rows=[json.loads(l) for l in cases.open(encoding='utf-8') if l.strip()]
try:
    git_head=subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip()
except Exception:
    git_head=None
target_rules=sorted(collections.Counter(r['target_rule_id'] for r in rows))
has_r08=any('R08' in r.get('rule_set_variant', []) or 'R08' in r.get('system_prompt', '') for r in rows)
manifest={
  'run_started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'research_question': 'Q1 target-balanced sampled rule-count experiment with Q2 injection set',
  'cases_file': str(cases.relative_to(root)),
  'trace_csv': str(trace.relative_to(root)),
  'cases_sha256': hashlib.sha256(cases.read_bytes()).hexdigest(),
  'case_count': len(rows),
  'target_turn_call_count': sum(int(r['turn_count']) for r in rows),
  'target_rule_distribution': dict(sorted(collections.Counter(r['target_rule_id'] for r in rows).items())),
  'rule_count_distribution': dict(sorted(collections.Counter(r['rule_count'] for r in rows).items())),
  'turn_count_distribution': dict(sorted(collections.Counter(r['turn_count'] for r in rows).items())),
  'condition_distribution': dict(sorted(collections.Counter(r['condition'] for r in rows).items())),
  'attack_order_variant_distribution': dict(sorted(collections.Counter(r.get('attack_order_variant') for r in rows).items())),
  'target_rules': target_rules,
  'r08_absent_verified': not has_r08,
  'target_model': os.environ['LLAMA_MODEL'],
  'judge_model': os.environ['GEMMA_MODEL'],
  'target_api_url': os.environ['TARGET_API_URL'],
  'judge_api_url': os.environ['TARGET_API_URL'],
  'target_concurrency': 8,
  'judge_concurrency': 4,
  'temperature': 0.0,
  'reps': 1,
  'git_head': git_head,
}
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=False, indent=2))
PY
}

validate_target() {
  python3 - <<'PY'
from pathlib import Path
import json, sys, collections, os
cases_path=Path(os.environ['CASES_FILE'])
out_path=Path(os.environ['RESULT_JSONL'])
summary_path=Path(os.environ['OUTPUT_DIR'])/'target_validation_summary.json'
cases=[json.loads(l) for l in cases_path.open(encoding='utf-8') if l.strip()]
records=[json.loads(l) for l in out_path.open(encoding='utf-8') if l.strip()] if out_path.exists() else []
case_by_id={c['case_id']: c for c in cases}
ids=[r.get('case_id') for r in records]
errors=[]
if len(records)!=len(cases): errors.append(f'record_count {len(records)} != {len(cases)}')
if set(ids)!=set(case_by_id): errors.append(f'case_id_set_mismatch missing={len(set(case_by_id)-set(ids))} extra={len(set(ids)-set(case_by_id))}')
if len(ids)!=len(set(ids)): errors.append(f'duplicate_records={len(ids)-len(set(ids))}')
if any('R08' in c.get('rule_set_variant', []) or 'R08' in c.get('system_prompt', '') for c in cases):
    errors.append('R08_present_in_generated_cases')
turn_errors=[]
error_responses=0
for r in records:
    cid=r.get('case_id')
    expected=case_by_id.get(cid, {}).get('turn_count')
    actual=len(r.get('turn_results', []))
    if expected != actual:
        turn_errors.append((cid, expected, actual))
    for t in r.get('turn_results', []):
        if str(t.get('response','')).startswith('[ERROR]'):
            error_responses += 1
if turn_errors: errors.append(f'turn_count_errors={turn_errors[:5]} total={len(turn_errors)}')
if error_responses: errors.append(f'error_responses={error_responses}')
summary={
  'records': len(records),
  'expected_records': len(cases),
  'total_turn_results': sum(len(r.get('turn_results', [])) for r in records),
  'expected_turn_results': sum(int(c['turn_count']) for c in cases),
  'target_rule_counts': dict(collections.Counter(c.get('target_rule_id') for c in cases)),
  'judge_status_counts': dict(collections.Counter(r.get('judge_status') for r in records)),
  'model_counts': dict(collections.Counter(r.get('model') for r in records)),
  'errors': errors,
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
if errors:
    sys.exit(20)
PY
}

validate_judge() {
  python3 - <<'PY'
from pathlib import Path
import json, sys, collections, datetime, os
root=Path(os.environ['ROOT'])
cases_path=Path(os.environ['CASES_FILE'])
out_path=Path(os.environ['RESULT_JSONL'])
output_dir=Path(os.environ['OUTPUT_DIR'])
cases=[json.loads(l) for l in cases_path.open(encoding='utf-8') if l.strip()]
records=[json.loads(l) for l in out_path.open(encoding='utf-8') if l.strip()]
def unresolved(score):
    if score.get('method') not in {'llm_judge','llm_language_judge'}: return False
    if score.get('pass') is not None: return False
    return not str(score.get('detail','')).lower().startswith('not applicable')
unresolved_scores=sum(1 for r in records for t in r.get('turn_results',[]) for s in t.get('scores',[]) if unresolved(s))
judge_scores=sum(1 for r in records for t in r.get('turn_results',[]) for s in t.get('scores',[]) if s.get('method') in {'llm_judge','llm_language_judge'})
summary={
  'validated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'records': len(records),
  'expected_records': len(cases),
  'total_turn_results': sum(len(r.get('turn_results', [])) for r in records),
  'expected_turn_results': sum(int(c['turn_count']) for c in cases),
  'target_rule_counts': dict(collections.Counter(c.get('target_rule_id') for c in cases)),
  'judge_status_counts': dict(collections.Counter(r.get('judge_status') for r in records)),
  'judge_model_counts': dict(collections.Counter(r.get('judge_model') for r in records)),
  'judge_provider_counts': dict(collections.Counter(r.get('judge_provider') for r in records)),
  'judge_scores': judge_scores,
  'unresolved_judge_scores': unresolved_scores,
}
errors=[]
if len(records) != len(cases): errors.append(f"record_count {len(records)} != {len(cases)}")
if unresolved_scores != 0: errors.append(f"unresolved_judge_scores={unresolved_scores}")
if summary['judge_status_counts'].get('complete') != len(cases):
    errors.append(f"complete_judge_records={summary['judge_status_counts'].get('complete', 0)} != {len(cases)}")
summary['errors']=errors
(output_dir/'judge_validation_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
# update manifest
manifest_path=Path(os.environ['MANIFEST'])
manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
manifest['run_completed_at']=summary['validated_at']
manifest['result_jsonl']=str(out_path.relative_to(root))
manifest['target_validation_summary']=str((output_dir/'target_validation_summary.json').relative_to(root))
manifest['judge_validation_summary']=str((output_dir/'judge_validation_summary.json').relative_to(root))
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
if errors:
    sys.exit(30)
PY
}

log "Q1 target-balanced Llama→Gemma run starting"
generate_target_balanced_cases
write_manifest_pre | tee "$LOG_DIR/manifest_pre.log"

log "Switching remote vLLM to Llama target container"
ssh_vllm "docker stop vllm-gemma >/dev/null 2>&1 || true; docker start vllm-server >/dev/null; docker ps --format '{{.Names}} {{.Status}} {{.Ports}}' | grep -E 'vllm|gemma' || true" | tee -a "$LOG_DIR/orchestrator.log"
wait_for_model "$LLAMA_MODEL" "llama" 240 5

case_count="$(wc -l < "$CASES_FILE" | tr -d ' ')"
log "Running target generation: ${case_count} cases, reps=1, concurrency=8"
VLLM_API_URL="$TARGET_API_URL" EVAL_MODEL_NAME="$LLAMA_MODEL" \
  .venv/bin/python scripts/run_experiment_fast.py \
  --models vllm \
  --reps 1 \
  --concurrency 8 \
  --temperature 0.0 \
  --cases-file "$CASES_FILE" \
  --output-dir "$OUTPUT_DIR" \
  2>&1 | tee "$LOG_DIR/target_llama.log"

log "Validating target generation output"
validate_target | tee "$LOG_DIR/target_validation.log"

log "Switching remote vLLM to Gemma judge container"
ssh_vllm "docker stop vllm-server >/dev/null 2>&1 || true; docker start vllm-gemma >/dev/null; docker ps --format '{{.Names}} {{.Status}} {{.Ports}}' | grep -E 'vllm|gemma' || true" | tee -a "$LOG_DIR/orchestrator.log"
wait_for_model "$GEMMA_MODEL" "gemma" 180 5

log "Running Gemma judge pass: concurrency=4"
JUDGE_PROVIDER=vllm \
JUDGE_API_URL="$TARGET_API_URL" \
JUDGE_MODEL_NAME="$GEMMA_MODEL" \
  .venv/bin/python scripts/run_experiment_fast.py \
  --judge-only \
  --concurrency 4 \
  --input "$RESULT_JSONL" \
  2>&1 | tee "$LOG_DIR/judge_gemma.log"

log "Validating judged output"
validate_judge | tee "$LOG_DIR/judge_validation.log"
log "Q1 target-balanced Llama→Gemma run complete"
