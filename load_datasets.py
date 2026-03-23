import os
import pandas as pd
import json
import glob

DATA_DIR = "/Users/kawai_tofu/GoogleCloud/Capstone_Dev/Total_Datasets"

def build_unified_eval_dataset():
    unified_queue = []

    # 1. MT-Eval (멀티턴 구조 보존)
    print("Loading MT-Eval...")
    mt_path = os.path.join(DATA_DIR, "MT-Eval/data/recollection_multi_global-inst.jsonl")
    try:
        mt_df = pd.read_json(mt_path, lines=True)
        for _, row in mt_df.iterrows():
            if 'conv' not in row or not isinstance(row['conv'], list) or len(row['conv']) == 0:
                continue
            
            conv = row['conv']
            system_instruction = ""
            turns = []
            
            # 구조 파악 후 턴별로 분리
            if 'user' in conv[0]: # {'user': '...', 'sys': '...'} 구조
                for t in conv:
                    turns.append({"user": t.get('user', ''), "target": t.get('sys', '') or t.get('assistant', '')})
            elif 'role' in conv[0]: # {'role': 'user', 'content': '...'} 구조
                for t in conv:
                    if t['role'] == 'system':
                        system_instruction = t['content']
                    elif t['role'] == 'user':
                        turns.append({"user": t['content'], "target": ""})
                    elif t['role'] in ['assistant', 'sys'] and turns:
                        turns[-1]["target"] = t['content']

            if turns:
                unified_queue.append({
                    "source": "MT-Eval",
                    "system_instruction": system_instruction,
                    "turns": turns
                })
    except Exception as e:
        print(f"MT-Eval 로드 에러: {e}")

    # 2. MultiChallenge (멀티턴 구조 보존)
    print("Loading MultiChallenge...")
    mc_path = os.path.join(DATA_DIR, "benchmark_questions.jsonl")
    try:
        mc_df = pd.read_json(mc_path, lines=True)
        retention_set = mc_df[mc_df['AXIS'].str.contains('MEMORY', na=False, case=False)] 
        
        for _, row in retention_set.iterrows():
            conversations = row.get("CONVERSATION", [])
            turns = []
            
            for t in conversations:
                if t["role"] == "user":
                    turns.append({"user": t["content"], "target": ""})
                elif t["role"] == "assistant" and turns:
                    turns[-1]["target"] = t["content"]
            
            # 마지막 타겟 질문이 별도로 있는 경우 추가
            target_q = row.get("TARGET_QUESTION", "")
            if target_q:
                turns.append({"user": target_q, "target": ""})

            if turns:
                unified_queue.append({
                    "source": "MultiChallenge",
                    "system_instruction": "",
                    "turns": turns
                })
    except Exception as e:
        print(f"MultiChallenge 로드 에러: {e}")

    # 3. StructFlowBench & 4. LIFBench (단일 턴도 동일한 스키마로 통일)
    # (파일 로드 로직은 기존과 동일하되 추가 방식만 변경)
    print("Loading StructFlowBench...")
    sf_path = os.path.join(DATA_DIR, "StructFlowBench.json")
    try:
        with open(sf_path, 'r', encoding='utf-8') as f:
            sf_data = json.load(f)
            
        for session in sf_data:
            whole_conv = session.get("whole_conv", [])
            if not whole_conv:
                continue
                
            turns = []
            for turn in whole_conv:
                user_text = turn.get("user prompt", "")
                target_text = turn.get("assistant answer", "")
                
                if user_text: # 사용자 질문이 존재하는 턴만 추가
                    turns.append({
                        "user": str(user_text),
                        "target": str(target_text)
                    })
            
            # 유효한 턴이 수집되었다면 큐에 추가
            if turns:
                unified_queue.append({
                    "source": "StructFlowBench",
                    "system_instruction": "", # 별도의 시스템 프롬프트가 없으므로 비워둠 (평가 코드가 첫 번째 질문을 Rule로 자동 할당함)
                    "turns": turns
                })
    except Exception as e:
        print(f"StructFlowBench 로드 에러: {e}")
    
    print("Loading LIFBench...")
    lif_pattern = os.path.join(DATA_DIR, "LIFBench-2024/data/prompts/**/*.json")
    for file_path in glob.glob(lif_pattern, recursive=True):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    unified_queue.append({
                        "source": f"LIFBench_{os.path.basename(file_path)}",
                        "system_instruction": "",
                        "turns": [{"user": item.get("prompt", ""), "target": str(item.get("label", ""))}]
                    })
        except Exception as e: pass

    # 5. 데이터 병합 및 저장
    print("Refining and deduplicating dataset...")
    df = pd.DataFrame(unified_queue)
    if not df.empty:
        output_file = os.path.join(DATA_DIR, "unified_evaluation_dataset.jsonl")
        df.to_json(output_file, orient="records", lines=True, force_ascii=False)
        print(f"✅ Success! Saved to {output_file}.")

if __name__ == "__main__":
    build_unified_eval_dataset()