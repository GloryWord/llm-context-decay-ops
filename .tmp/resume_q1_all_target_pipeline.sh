#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops"
cd "$ROOT"
CASES="$ROOT/data/processed/q1_sampled_q2_injection_cases.jsonl"
TRACE="$ROOT/data/processed/q1_sampled_q2_injection_cases_trace.csv"
OUTPUT_DIR="$ROOT/data/outputs/2026-05-18_q1_sampled_local_llama_gemma"
RESULT="$OUTPUT_DIR/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl"
LOG_DIR="$OUTPUT_DIR/logs"
TARGET_API_URL="http://210.179.28.26:18000/v1/chat/completions"
MODELS_API_URL="http://210.179.28.26:18000/v1/models"
LLAMA_MODEL="hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
GEMMA_MODEL="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -J mhncity@210.179.28.26)
VLLM_HOST="mhncity@172.30.1.13"
TARGET_CONCURRENCY="${TARGET_CONCURRENCY:-12}"
JUDGE_CONCURRENCY="${JUDGE_CONCURRENCY:-6}"
mkdir -p "$LOG_DIR"
log(){ printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" | tee -a "$LOG_DIR/resume_all_target.log"; }
ssh_vllm(){ ssh "${SSH_OPTS[@]}" "$VLLM_HOST" "$@"; }
line_count(){ [[ -f "$1" ]] && wc -l < "$1" | tr -d ' ' || echo 0; }
wait_model(){ local expected="$1" label="$2" attempts="${3:-240}"; for i in $(seq 1 "$attempts"); do body=$(curl -sS --connect-timeout 3 --max-time 10 "$MODELS_API_URL" 2>/dev/null || true); if printf '%s' "$body" | grep -Fq "$expected"; then log "$label ready after $i"; return 0; fi; sleep 5; done; return 1; }
ensure_cases(){ if [[ ! -f "$CASES" ]] || [[ $(line_count "$CASES") -ne 3069 ]]; then log "regenerating all-target cases"; .venv/bin/python scripts/generate_q1_sampled_cases.py --all-target-rules --output "$CASES" --trace-csv "$TRACE"; cp -p "$CASES" data/processed/Research_Question_1_Data/q1_sampled_q2_injection_cases.jsonl; cp -p "$TRACE" data/processed/Research_Question_1_Data/q1_sampled_q2_injection_cases_trace.csv; fi; }
validate_target(){ .venv/bin/python - <<'PY'
from pathlib import Path
import json, sys, collections
root=Path('/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops')
cases=[json.loads(l) for l in (root/'data/processed/q1_sampled_q2_injection_cases.jsonl').open(encoding='utf-8') if l.strip()]
records=[json.loads(l) for l in (root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl').open(encoding='utf-8') if l.strip()]
errors=[]
if len(records)!=3069: errors.append(f'records {len(records)} != 3069')
if {r['case_id'] for r in records}!={c['case_id'] for c in cases}: errors.append('case id set mismatch')
if any(len(r.get('turn_results',[])) != next(c['turn_count'] for c in cases if c['case_id']==r['case_id']) for r in records): errors.append('turn count mismatch')
summary={'records':len(records),'expected_records':len(cases),'total_turn_results':sum(len(r.get('turn_results',[])) for r in records),'expected_turn_results':sum(c['turn_count'] for c in cases),'judge_status_counts':dict(collections.Counter(r.get('judge_status') for r in records)),'target_rule_counts':dict(sorted(collections.Counter(r.get('target_rule_id') for r in records).items())),'errors':errors}
(root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/target_validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
if errors: sys.exit(20)
PY
}
validate_judge(){ .venv/bin/python - <<'PY'
from pathlib import Path
import json, sys, collections, hashlib, datetime
root=Path('/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops')
p=root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl'
records=[json.loads(l) for l in p.open(encoding='utf-8') if l.strip()]
def unresolved(s): return s.get('method') in {'llm_judge','llm_language_judge'} and s.get('pass') is None and not str(s.get('detail','')).lower().startswith('not applicable')
unres=sum(1 for r in records for t in r.get('turn_results',[]) for s in t.get('scores',[]) if unresolved(s))
summary={'validated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'records':len(records),'total_turn_results':sum(len(r.get('turn_results',[])) for r in records),'judge_status_counts':dict(collections.Counter(r.get('judge_status') for r in records)),'judge_model_counts':dict(collections.Counter(r.get('judge_model') for r in records)),'judge_provider_counts':dict(collections.Counter(r.get('judge_provider') for r in records)),'unresolved_judge_scores':unres,'result_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/judge_validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
manifest_path=root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/run_manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
manifest.update({'run_completed_at':summary['validated_at'],'result_jsonl':'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl','result_jsonl_sha256_after_judge':summary['result_sha256'],'target_validation_summary':'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/target_validation_summary.json','judge_validation_summary':'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/judge_validation_summary.json'})
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
if len(records)!=3069 or unres!=0 or summary['judge_status_counts'].get('complete')!=3069: sys.exit(30)
PY
}
judge_force_rejudge_flag(){ .venv/bin/python - <<'PY'
from pathlib import Path
import json
p=Path('data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl')
if not p.exists():
    print("")
    raise SystemExit
records=[json.loads(l) for l in p.open(encoding='utf-8') if l.strip()]
pending=0
failed_non_pending=0
for r in records:
    for t in r.get('turn_results',[]):
        for s in t.get('scores',[]):
            if s.get('method') not in {'llm_judge','llm_language_judge'} or s.get('pass') is not None:
                continue
            detail=str(s.get('detail','')).lower()
            if detail.startswith('not applicable'):
                continue
            if 'pending' in detail:
                pending += 1
            else:
                failed_non_pending += 1
print("--force-rejudge" if failed_non_pending and not pending else "")
PY
}
ensure_cases
if [[ $(line_count "$RESULT") -lt 3069 ]]; then
  log "resuming target generation from $(line_count "$RESULT")/3069 records"
  ssh_vllm "docker stop vllm-gemma >/dev/null 2>&1 || true; docker start vllm-server >/dev/null" || true
  wait_model "$LLAMA_MODEL" llama
  VLLM_API_URL="$TARGET_API_URL" EVAL_MODEL_NAME="$LLAMA_MODEL" .venv/bin/python scripts/run_experiment_fast.py --models vllm --reps 1 --concurrency "$TARGET_CONCURRENCY" --temperature 0.0 --cases-file "$CASES" --output-dir "$OUTPUT_DIR" 2>&1 | tee -a "$LOG_DIR/target_llama_all_target.log"
fi
validate_target | tee -a "$LOG_DIR/target_validation_all_target.log"
if ! [[ -f "$OUTPUT_DIR/judge_validation_summary.json" ]] || ! python3 - <<'PY'
import json, pathlib, sys
p=pathlib.Path('data/outputs/2026-05-18_q1_sampled_local_llama_gemma/judge_validation_summary.json')
if not p.exists(): sys.exit(1)
d=json.loads(p.read_text()); sys.exit(0 if d.get('records')==3069 and d.get('unresolved_judge_scores')==0 and d.get('judge_status_counts',{}).get('complete')==3069 else 1)
PY
then
  log "running/resuming judge pass"
  ssh_vllm "docker stop vllm-server >/dev/null 2>&1 || true; docker start vllm-gemma >/dev/null" || true
  wait_model "$GEMMA_MODEL" gemma
  FORCE_FLAG="$(judge_force_rejudge_flag)"
  if [[ -n "$FORCE_FLAG" ]]; then
    log "detected non-pending unresolved judge failures; using $FORCE_FLAG for recovery"
  fi
  JUDGE_PROVIDER=vllm JUDGE_API_URL="$TARGET_API_URL" JUDGE_MODEL_NAME="$GEMMA_MODEL" .venv/bin/python scripts/run_experiment_fast.py --judge-only $FORCE_FLAG --concurrency "$JUDGE_CONCURRENCY" --input "$RESULT" 2>&1 | tee -a "$LOG_DIR/judge_gemma_all_target.log"
fi
validate_judge | tee -a "$LOG_DIR/judge_validation_all_target.log"
.tmp/postprocess_q1_all_target_after_run.sh
log "resume pipeline complete"
