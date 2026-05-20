#!/usr/bin/env python3
from __future__ import annotations
import collections, hashlib, json, sys, time
from pathlib import Path

def load_jsonl_strict(path: Path):
    b = path.read_bytes()
    nul = b.count(b"\x00")
    rows=[]; bad=[]
    for i,line in enumerate(b.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line.decode('utf-8')))
        except Exception as e:
            bad.append({'line':i,'error':repr(e),'prefix':line[:120].decode('utf-8','replace')})
    return rows,nul,bad

def sha(path: Path):
    h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()

def main():
    if len(sys.argv) != 2:
        print('usage: aggregate_clean_extended_adaptive.py OUTDIR', file=sys.stderr); return 2
    out=Path(sys.argv[1])
    source=Path('.tmp/q1_finish_reason_rerun/clean_n83_20260518T191600+0900/replay_metadata_r07_false_truncation_suspect.jsonl')
    source_rows, source_nul, source_bad = load_jsonl_strict(source)
    cohort=[r for r in source_rows if r.get('ok') is True and r.get('finish_reason')=='length' and r.get('max_tokens')==512 and (r.get('usage') or {}).get('completion_tokens')==512]
    source_keys={(r['case_id'], int(r['turn'])) for r in cohort}
    final_rows=[]; attempt_rows=[]; shard_checks=[]; bad_files=[]; nul_files=[]
    for i in range(4):
        sd=out/f'shard_{i}'
        mp=sd/f'manifest_shard{i}.json'; sp=sd/f'summary_shard{i}.json'; fp=sd/f'final_shard{i}.jsonl'; ap=sd/f'attempts_shard{i}.jsonl'
        manifest=json.loads(mp.read_text(encoding='utf-8'))
        summary=json.loads(sp.read_text(encoding='utf-8'))
        finals,nul,bad=load_jsonl_strict(fp)
        attempts,anul,abad=load_jsonl_strict(ap)
        if nul: nul_files.append({'path':str(fp),'nul_count':nul})
        if anul: nul_files.append({'path':str(ap),'nul_count':anul})
        if bad: bad_files.append({'path':str(fp),'bad':bad})
        if abad: bad_files.append({'path':str(ap),'bad':abad})
        shard_checks.append({
            'shard_index':i,
            'manifest_target_count':manifest.get('target_count'),
            'summary_target_count':summary.get('target_count'),
            'summary_ok_count':summary.get('ok_count'),
            'final_line_count':len(finals),
            'attempt_line_count':len(attempts),
            'summary_finish_reason_counts':summary.get('final_finish_reason_counts'),
            'summary_final_cap_counts':summary.get('final_cap_counts'),
            'summary_resolved_non_length_count':summary.get('resolved_non_length_count'),
            'summary_still_cap_limited_at_final_cap_count':summary.get('still_cap_limited_at_final_cap_count'),
            'manifest_path':str(mp), 'summary_path':str(sp), 'final_path':str(fp), 'attempts_path':str(ap),
            'final_sha256':sha(fp), 'attempts_sha256':sha(ap),
        })
        final_rows.extend(finals); attempt_rows.extend(attempts)
    final_keys=[(r['case_id'], int(r['turn'])) for r in final_rows]
    key_counts=collections.Counter(final_keys)
    dup=[{'case_id':k[0],'turn':k[1],'count':c} for k,c in key_counts.items() if c>1]
    missing=sorted(source_keys-set(final_keys))
    extra=sorted(set(final_keys)-source_keys)
    final_rows.sort(key=lambda r:(str(r.get('case_id')), int(r.get('turn',0))))
    attempt_rows.sort(key=lambda r:(str(r.get('case_id')), int(r.get('turn',0)), int(r.get('attempt_no',0)), int(r.get('max_tokens',0))))
    agg_final=out/'replay_extended_adaptive_clean_aggregated.jsonl'
    agg_attempts=out/'attempts_extended_adaptive_clean_aggregated.jsonl'
    agg_final.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in final_rows), encoding='utf-8')
    agg_attempts.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in attempt_rows), encoding='utf-8')
    finish=collections.Counter(str(r.get('finish_reason')) for r in final_rows)
    cap=collections.Counter(str(r.get('max_tokens')) for r in final_rows)
    attempts=collections.Counter(str(r.get('attempt_count')) for r in final_rows)
    completion_eq_cap=sum(1 for r in final_rows if ((r.get('usage') or {}).get('completion_tokens') == r.get('max_tokens')))
    q00020=[r for r in final_rows if r.get('case_id')=='q1samp_00020' and int(r.get('turn',0))==15]
    summary={
        'created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'authoritative': True,
        'discarded_outdirs':['.tmp/q1_finish_reason_rerun/extended_adaptive_20260518T193519+0900'],
        'outdir':str(out),
        'source_metadata':str(source),
        'source_rows':len(source_rows),
        'source_bad_json_lines':source_bad,
        'source_nul_count':source_nul,
        'source_cohort_count_length512':len(cohort),
        'selection_rule':"ok=true AND finish_reason='length' AND usage.completion_tokens=max_tokens=512",
        'policy_ladder':[1024,1536,2048,3072],
        'terminal_bound':3072,
        'shard_checks':shard_checks,
        'final_row_count':len(final_rows),
        'attempt_row_count':len(attempt_rows),
        'unique_case_turn_count':len(set(final_keys)),
        'missing_case_turns':[{'case_id':c,'turn':t} for c,t in missing],
        'extra_case_turns':[{'case_id':c,'turn':t} for c,t in extra],
        'duplicate_case_turns':dup,
        'bad_json_files':bad_files,
        'nul_files':nul_files,
        'final_finish_reason_counts':dict(finish),
        'final_cap_counts':dict(cap),
        'attempt_count_distribution':dict(attempts),
        'resolved_non_length_count':sum(1 for r in final_rows if r.get('resolved_non_length')),
        'still_cap_limited_at_final_cap_count':sum(1 for r in final_rows if r.get('still_cap_limited_at_final_cap')),
        'completion_tokens_eq_selected_max_tokens_count':completion_eq_cap,
        'q1samp_00020_turn15': q00020,
        'aggregate_final_jsonl':str(agg_final),
        'aggregate_attempts_jsonl':str(agg_attempts),
        'aggregate_final_sha256':sha(agg_final),
        'aggregate_attempts_sha256':sha(agg_attempts),
    }
    summary['validation_passed']= (
        len(cohort)==79 and len(final_rows)==79 and len(set(final_keys))==79 and not missing and not extra and not dup and not bad_files and not nul_files and sum(s['manifest_target_count'] for s in shard_checks)==79 and all(s['final_line_count']==s['manifest_target_count'] for s in shard_checks)
    )
    sp=out/'summary_extended_adaptive_clean.json'
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    md=out/'summary_extended_adaptive_clean.md'
    md.write_text(f"""# Q1 clean extended adaptive rerun summary\n\n- Validation passed: `{summary['validation_passed']}`\n- Source cohort: {len(cohort)} rows selected from clean N=83 where finish_reason=length and completion_tokens=max_tokens=512.\n- Final rows: {len(final_rows)}; attempts: {len(attempt_rows)}; unique case-turns: {len(set(final_keys))}.\n- Final finish reasons: {dict(finish)}\n- Final selected caps: {dict(cap)}\n- Resolved non-length: {summary['resolved_non_length_count']}\n- Still cap-limited at 3072: {summary['still_cap_limited_at_final_cap_count']}\n- q1samp_00020 turn 15: finish_reason={q00020[0].get('finish_reason') if q00020 else 'MISSING'}, max_tokens={q00020[0].get('max_tokens') if q00020 else 'MISSING'}, completion_tokens={(q00020[0].get('usage') or {}).get('completion_tokens') if q00020 else 'MISSING'}\n\nAuthoritative outdir: `{out}`\nDiscarded contaminated outdir: `.tmp/q1_finish_reason_rerun/extended_adaptive_20260518T193519+0900`\n""", encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['validation_passed'] else 1
if __name__=='__main__': raise SystemExit(main())
