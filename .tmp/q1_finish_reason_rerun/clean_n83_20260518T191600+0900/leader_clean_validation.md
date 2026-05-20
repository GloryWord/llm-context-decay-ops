# Q1 clean N=83 finish_reason validation

- outdir: `.tmp/q1_finish_reason_rerun/clean_n83_20260518T191600+0900`
- parsed rows: 83 / bad JSON lines: 0
- ok_count/error_count: 83/0
- finish_reason_counts: `{'length': 79, 'stop': 4}`
- completion_tokens == 512: 79
- hit max token rule count: 79
- q1samp_00020 turn15: `[{'case_id': 'q1samp_00020', 'turn': 15, 'finish_reason': 'length', 'usage': {'prompt_tokens': 7572, 'total_tokens': 8084, 'completion_tokens': 512, 'prompt_tokens_details': None}, 'max_tokens': 512, 'model_returned': 'hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4', 'response_length': 868, 'original_response_length': 868, 'response_equals_original': True}]`

Interpretation: finish_reason=`length` with usage.completion_tokens == configured max_tokens(512) is direct evidence of output cap truncation. finish_reason=`stop` with completion_tokens below 512 is evidence the model stopped before the cap.
