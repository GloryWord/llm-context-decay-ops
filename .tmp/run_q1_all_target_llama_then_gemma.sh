#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops"
cd "$ROOT"

CASES_FILE="$ROOT/data/processed/q1_sampled_q2_injection_cases.jsonl"
TRACE_FILE="$ROOT/data/processed/q1_sampled_q2_injection_cases_trace.csv"
RQ1_TRACE_FILE="$ROOT/data/processed/Research_Question_1_Data/q1_sampled_q2_injection_cases_trace.csv"
RQ1_CASES_FILE="$ROOT/data/processed/Research_Question_1_Data/q1_sampled_q2_injection_cases.jsonl"
OUTPUT_DIR="$ROOT/data/outputs/2026-05-18_q1_sampled_local_llama_gemma"
LOG_DIR="$OUTPUT_DIR/logs"
MANIFEST="$OUTPUT_DIR/run_manifest.json"
TARGET_API_URL="http://210.179.28.26:18000/v1/chat/completions"
MODELS_API_URL="http://210.179.28.26:18000/v1/models"
LLAMA_MODEL="hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
GEMMA_MODEL="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -J mhncity@210.179.28.26)
VLLM_HOST="mhncity@172.30.1.13"
RESULT_JSONL="$OUTPUT_DIR/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl"
TARGET_CONCURRENCY="${TARGET_CONCURRENCY:-12}"
JUDGE_CONCURRENCY="${JUDGE_CONCURRENCY:-6}"
EXPECTED_CASE_COUNT="3069"
EXPECTED_TURN_CALLS="25668"
RUN_LABEL="q1_all_target_balanced_$(date '+%Y%m%dT%H%M%S%z')"
ARCHIVE_DIR="$ROOT/.tmp/q1_target_balanced_archive/$RUN_LABEL"

mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$ROOT/data/processed/Research_Question_1_Data"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" | tee -a "$LOG_DIR/orchestrator_all_target.log"
}

ssh_vllm() {
  ssh "${SSH_OPTS[@]}" "$VLLM_HOST" "$@"
}

wait_for_model() {
  local expected="$1"
  local label="$2"
  local attempts="${3:-180}"
  local sleep_s="${4:-5}"
  log "waiting for $label model endpoint: $expected"
  for i in $(seq 1 "$attempts"); do
    local body
    body=$(curl -sS --connect-timeout 3 --max-time 10 "$MODELS_API_URL" 2>/dev/null || true)
    printf '%s\n' "$body" > "$LOG_DIR/models_${label}_all_target_attempt_${i}.json"
    if printf '%s' "$body" | grep -Fq "$expected"; then
      log "$label endpoint ready after attempt $i"
      curl -sS --connect-timeout 5 --max-time 20 "$MODELS_API_URL" | tee "$LOG_DIR/models_${label}_all_target_ready.json" >/dev/null
      return 0
    fi
    if (( i % 12 == 0 )); then
      log "$label wait attempt $i/$attempts still not ready"
      ssh_vllm "docker ps --format '{{.Names}} {{.Status}} {{.Ports}}' | grep -E 'vllm|gemma' || true" | tee -a "$LOG_DIR/orchestrator_all_target.log" || true
    fi
    sleep "$sleep_s"
  done
  log "ERROR: $label endpoint did not expose expected model: $expected"
  return 1
}

archive_previous_outputs() {
  log "Archiving previous R03-only/default artifacts to $ARCHIVE_DIR"
  for path in \
    "$CASES_FILE" \
    "$TRACE_FILE" \
    "$RQ1_CASES_FILE" \
    "$RQ1_TRACE_FILE" \
    "$RESULT_JSONL" \
    "$OUTPUT_DIR/target_validation_summary.json" \
    "$OUTPUT_DIR/judge_validation_summary.json" \
    "$OUTPUT_DIR/metadata_enrichment_summary.json" \
    "$MANIFEST" \
    "$OUTPUT_DIR/ai_adjusted/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl" \
    "$OUTPUT_DIR/ai_adjusted/ai_adjusted_score_changes.csv"; do
    if [[ -e "$path" ]]; then
      cp -p "$path" "$ARCHIVE_DIR/$(basename "$path")"
    fi
  done
  if [[ -d "$OUTPUT_DIR/ai_adjusted/q1_visualization" ]]; then
    mkdir -p "$ARCHIVE_DIR/ai_adjusted"
    rsync -a "$OUTPUT_DIR/ai_adjusted/q1_visualization" "$ARCHIVE_DIR/ai_adjusted/" >/dev/null 2>&1 || cp -R "$OUTPUT_DIR/ai_adjusted/q1_visualization" "$ARCHIVE_DIR/ai_adjusted/"
  fi
  if [[ -d "$OUTPUT_DIR/reaggregated" ]]; then
    mkdir -p "$ARCHIVE_DIR/raw_reaggregated"
    rsync -a "$OUTPUT_DIR/reaggregated/" "$ARCHIVE_DIR/raw_reaggregated/" >/dev/null 2>&1 || true
  fi
  if [[ -d "$OUTPUT_DIR/ai_adjusted/reaggregated" ]]; then
    mkdir -p "$ARCHIVE_DIR/ai_adjusted_reaggregated"
    rsync -a "$OUTPUT_DIR/ai_adjusted/reaggregated/" "$ARCHIVE_DIR/ai_adjusted_reaggregated/" >/dev/null 2>&1 || true
  fi
}

generate_cases() {
  log "Generating all-target balanced Q1 cases (R08 absent/Q2 profile)"
  .venv/bin/python scripts/generate_q1_sampled_cases.py \
    --all-target-rules \
    --output "$CASES_FILE" \
    --trace-csv "$TRACE_FILE" \
    2>&1 | tee "$LOG_DIR/generate_all_target_cases.log"
  cp -p "$CASES_FILE" "$RQ1_CASES_FILE"
  cp -p "$TRACE_FILE" "$RQ1_TRACE_FILE"
}

write_manifest_pre() {
  .venv/bin/python - <<'PY'
from pathlib import Path
import json, hashlib, collections, datetime, subprocess
root=Path('/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops')
cases=root/'data/processed/q1_sampled_q2_injection_cases.jsonl'
out=root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/run_manifest.json'
rows=[json.loads(l) for l in cases.open(encoding='utf-8') if l.strip()]
try:
    git_head=subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip()
except Exception:
    git_head=None
manifest={
  'run_started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'research_question': 'Q1 target-balanced sampled rule-count experiment with Q2 injection set',
  'design_update': 'all Q2-available target rules balanced; R08 absent/excluded',
  'cases_file': str(cases.relative_to(root)),
  'trace_file': 'data/processed/q1_sampled_q2_injection_cases_trace.csv',
  'rq1_trace_file': 'data/processed/Research_Question_1_Data/q1_sampled_q2_injection_cases_trace.csv',
  'cases_sha256': hashlib.sha256(cases.read_bytes()).hexdigest(),
  'case_count': len(rows),
  'target_turn_call_count': sum(int(r['turn_count']) for r in rows),
  'rule_count_distribution': dict(sorted(collections.Counter(r['rule_count'] for r in rows).items())),
  'turn_count_distribution': dict(sorted(collections.Counter(r['turn_count'] for r in rows).items())),
  'condition_distribution': dict(sorted(collections.Counter(r['condition'] for r in rows).items())),
  'attack_order_variant_distribution': dict(sorted(collections.Counter(r.get('attack_order_variant') for r in rows).items())),
  'target_rule_distribution': dict(sorted(collections.Counter(r.get('target_rule_id') for r in rows).items())),
  'target_rule_category_distribution': dict(sorted(collections.Counter(r.get('target_rule_category') for r in rows).items())),
  'excluded_rule_ids': ['R08'],
  'target_model': 'hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4',
  'judge_model': 'cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit',
  'target_api_url': 'http://210.179.28.26:18000/v1/chat/completions',
  'judge_api_url': 'http://210.179.28.26:18000/v1/chat/completions',
  'target_concurrency': int(__import__('os').environ.get('TARGET_CONCURRENCY','12')),
  'judge_concurrency': int(__import__('os').environ.get('JUDGE_CONCURRENCY','6')),
  'temperature': 0.0,
  'reps': 1,
  'git_head': git_head,
  'run_experiment_fast_metadata_capture': True,
}
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=False, indent=2))
if len(rows) != 3069 or sum(int(r['turn_count']) for r in rows) != 25668:
    raise SystemExit('unexpected generated case/turn count')
PY
}

clear_previous_run_rows() {
  log "Clearing old checkpoint/result files that would conflict by case_id"
  rm -f "$RESULT_JSONL"
  rm -f "$OUTPUT_DIR/target_validation_summary.json" "$OUTPUT_DIR/judge_validation_summary.json"
  rm -rf "$OUTPUT_DIR/reaggregated" "$OUTPUT_DIR/ai_adjusted/reaggregated"
  mkdir -p "$OUTPUT_DIR/ai_adjusted"
  rm -f "$OUTPUT_DIR/ai_adjusted/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl"
  rm -f "$OUTPUT_DIR/ai_adjusted/ai_adjusted_score_changes.csv"
}

validate_target() {
  .venv/bin/python - <<'PY'
from pathlib import Path
import json, sys, collections
root=Path('/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops')
cases_path=root/'data/processed/q1_sampled_q2_injection_cases.jsonl'
out_path=root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl'
cases=[json.loads(l) for l in cases_path.open(encoding='utf-8') if l.strip()]
records=[json.loads(l) for l in out_path.open(encoding='utf-8') if l.strip()] if out_path.exists() else []
case_by_id={c['case_id']: c for c in cases}
ids=[r.get('case_id') for r in records]
errors=[]
if len(records)!=len(cases): errors.append(f'record_count {len(records)} != {len(cases)}')
if set(ids)!=set(case_by_id): errors.append(f'case_id_set_mismatch missing={len(set(case_by_id)-set(ids))} extra={len(set(ids)-set(case_by_id))}')
if len(ids)!=len(set(ids)): errors.append(f'duplicate_records={len(ids)-len(set(ids))}')
turn_errors=[]; error_responses=0; finish=collections.Counter(); hit_512=0
for r in records:
    cid=r.get('case_id')
    expected=case_by_id.get(cid, {}).get('turn_count')
    actual=len(r.get('turn_results', []))
    if expected != actual:
        turn_errors.append((cid, expected, actual))
    for t in r.get('turn_results', []):
        if str(t.get('response','')).startswith('[ERROR]'):
            error_responses += 1
        finish[str(t.get('target_finish_reason'))] += 1
        usage=t.get('target_usage') or {}
        if usage.get('completion_tokens') == 512:
            hit_512 += 1
if turn_errors: errors.append(f'turn_count_errors={turn_errors[:5]} total={len(turn_errors)}')
if error_responses: errors.append(f'error_responses={error_responses}')
summary={
  'records': len(records),
  'expected_records': len(cases),
  'total_turn_results': sum(len(r.get('turn_results', [])) for r in records),
  'expected_turn_results': sum(int(c['turn_count']) for c in cases),
  'judge_status_counts': dict(collections.Counter(r.get('judge_status') for r in records)),
  'model_counts': dict(collections.Counter(r.get('model') for r in records)),
  'target_rule_counts': dict(sorted(collections.Counter(r.get('target_rule_id') for r in records).items())),
  'finish_reason_counts': dict(finish),
  'completion_tokens_eq_512_turns': hit_512,
  'errors': errors,
}
(root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/target_validation_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
if errors or len(records)!=3069 or summary['total_turn_results']!=25668:
    sys.exit(20)
PY
}

validate_judge() {
  .venv/bin/python - <<'PY'
from pathlib import Path
import json, sys, collections, datetime, hashlib
root=Path('/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops')
out_path=root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl'
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
  'total_turn_results': sum(len(r.get('turn_results', [])) for r in records),
  'judge_status_counts': dict(collections.Counter(r.get('judge_status') for r in records)),
  'judge_model_counts': dict(collections.Counter(r.get('judge_model') for r in records)),
  'judge_provider_counts': dict(collections.Counter(r.get('judge_provider') for r in records)),
  'target_rule_counts': dict(sorted(collections.Counter(r.get('target_rule_id') for r in records).items())),
  'judge_scores': judge_scores,
  'unresolved_judge_scores': unresolved_scores,
  'result_sha256': hashlib.sha256(out_path.read_bytes()).hexdigest(),
}
(root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/judge_validation_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
manifest_path=root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/run_manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
manifest['run_completed_at']=summary['validated_at']
manifest['result_jsonl']='data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl'
manifest['result_jsonl_sha256_after_judge']=summary['result_sha256']
manifest['target_validation_summary']='data/outputs/2026-05-18_q1_sampled_local_llama_gemma/target_validation_summary.json'
manifest['judge_validation_summary']='data/outputs/2026-05-18_q1_sampled_local_llama_gemma/judge_validation_summary.json'
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
if len(records)!=3069 or unresolved_scores!=0 or summary['judge_status_counts'].get('complete')!=3069:
    sys.exit(30)
PY
}

log "Q1 all-target balanced Llama→Gemma run starting"
archive_previous_outputs
generate_cases
TARGET_CONCURRENCY="$TARGET_CONCURRENCY" JUDGE_CONCURRENCY="$JUDGE_CONCURRENCY" write_manifest_pre | tee "$LOG_DIR/manifest_all_target_pre.log"
clear_previous_run_rows

log "Switching remote vLLM to Llama target container"
ssh_vllm "docker stop vllm-gemma >/dev/null 2>&1 || true; docker start vllm-server >/dev/null; docker ps --format '{{.Names}} {{.Status}} {{.Ports}}' | grep -E 'vllm|gemma' || true" | tee -a "$LOG_DIR/orchestrator_all_target.log"
wait_for_model "$LLAMA_MODEL" "llama" 240 5

log "Running target generation: $EXPECTED_CASE_COUNT cases, $EXPECTED_TURN_CALLS turns, reps=1, concurrency=$TARGET_CONCURRENCY"
VLLM_API_URL="$TARGET_API_URL" EVAL_MODEL_NAME="$LLAMA_MODEL" \
  .venv/bin/python scripts/run_experiment_fast.py \
  --models vllm \
  --reps 1 \
  --concurrency "$TARGET_CONCURRENCY" \
  --temperature 0.0 \
  --cases-file "$CASES_FILE" \
  --output-dir "$OUTPUT_DIR" \
  2>&1 | tee "$LOG_DIR/target_llama_all_target.log"

log "Validating target generation output"
validate_target | tee "$LOG_DIR/target_validation_all_target.log"

log "Switching remote vLLM to Gemma judge container"
ssh_vllm "docker stop vllm-server >/dev/null 2>&1 || true; docker start vllm-gemma >/dev/null; docker ps --format '{{.Names}} {{.Status}} {{.Ports}}' | grep -E 'vllm|gemma' || true" | tee -a "$LOG_DIR/orchestrator_all_target.log"
wait_for_model "$GEMMA_MODEL" "gemma" 240 5

log "Running Gemma judge pass: concurrency=$JUDGE_CONCURRENCY"
JUDGE_PROVIDER=vllm \
JUDGE_API_URL="$TARGET_API_URL" \
JUDGE_MODEL_NAME="$GEMMA_MODEL" \
  .venv/bin/python scripts/run_experiment_fast.py \
  --judge-only \
  --concurrency "$JUDGE_CONCURRENCY" \
  --input "$RESULT_JSONL" \
  2>&1 | tee "$LOG_DIR/judge_gemma_all_target.log"

log "Validating judged output"
validate_judge | tee "$LOG_DIR/judge_validation_all_target.log"
log "Q1 all-target balanced Llama→Gemma run complete"
