import asyncio
import aiohttp
import numpy as np
import re
import os
import json

# ===== 설정 =====
API_KEY = os.getenv("OPENROUTER_API_KEY") or "YOUR_OPENROUTER_API_KEY" 
JUDGE_MODEL = "openai/gpt-4o-mini"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

INPUT_FILE = "test_inference_output.jsonl" 
OUTPUT_FILE = "final_evaluation_results.jsonl"

def calculate_ifs(scores):
    """IFS(Instruction Following Score) 변동성 계산"""
    if len(scores) < 2: return 0.0
    mean_y = np.mean(scores)
    std_y = np.std(scores, ddof=1)
    return std_y / mean_y if mean_y != 0 else float('inf')

async def evaluate_turn_llm_judge(session, rule, user_input, model_output):
    """
    rule: 세션 전체에 적용되는 핵심 지시사항
    user_input: 현재 턴의 질문
    model_output: 현재 턴의 AI 답변
    """
    judge_prompt = f"""
    당신은 엄격한 LLM 지시 준수 평가관입니다.
    AI가 아래의 [핵심 지시사항]을 잊지 않고 완벽하게 유지하며 [현재 사용자 질문]에 답했는지 1점부터 5점 사이로 평가하세요.
    
    [핵심 지시사항]: {rule}
    [현재 사용자 질문]: {user_input}
    [AI 답변]: {model_output}
    
    오직 1~5 사이의 정수 숫자 하나만 출력하세요 (예: 5):"""
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": "http://localhost",
    }
    payload = {
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": judge_prompt}],
        "temperature": 0.0
    }
    
    try:
        async with session.post(API_URL, headers=headers, json=payload) as response:
            result = await response.json()
            score_text = result.get("choices", [{}])[0].get("message", {}).get("content", "1")
            
            # 1. 정규식으로 숫자 추출
            match = re.search(r'\d+', score_text)
            if match:
                raw_score = float(match.group())
                # 2. 방어 로직: 1.0 ~ 5.0 사이로 강제 클램핑(Clamping)
                return max(1.0, min(raw_score, 5.0))
            else:
                return 1.0
    except Exception as e:
        print(f"❌ Judge API Error: {e}")
        return 1.0

async def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 파일을 찾을 수 없습니다: {INPUT_FILE}")
        return

    results = []
    print(f"🧐 {INPUT_FILE} 통합 채점(싱글/멀티턴)을 시작합니다...")

    async with aiohttp.ClientSession() as session:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line_idx, line in enumerate(lines):
            data = json.loads(line)
            source = data.get("source", "Unknown")
            
            system_inst = data.get("system_instruction", "")
            turns = data.get("turns", [])
            
            if not turns: continue
            
            rule = system_inst if system_inst else turns[0].get("user", "")
            turn_scores = [] 
            
            print(f"\n[{line_idx+1}] Source: {source} | Rule: {rule[:50]}...")

            for t_idx, turn in enumerate(turns):
                user_input = turn.get("user", "")
                model_output = turn.get("model_output", "")
                
                score = await evaluate_turn_llm_judge(session, rule, user_input, model_output)
                turn_scores.append(score)
                
                current_ifs = calculate_ifs(turn_scores)
                
                turn["judge_score"] = score
                turn["current_ifs"] = current_ifs
                
                print(f"  -> Turn {t_idx+1} | Score: {score} | IFS: {current_ifs:.4f}")
            
            # 3. LIFBench와 같은 싱글턴 모델 평가를 위한 세션 평균 점수 산출
            data["session_avg_score"] = float(np.mean(turn_scores))
            
            results.append(data)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for res in results:
            f.write(json.dumps(res, ensure_ascii=False) + '\n')
            
    print("\n" + "=" * 50)
    print(f"✅ 채점 완료! 결과 저장됨: {OUTPUT_FILE}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())