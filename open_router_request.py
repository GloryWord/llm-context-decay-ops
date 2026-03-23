import asyncio
import aiohttp
import json
import os

# ===== 설정 =====
API_KEY = os.getenv("OPENROUTER_API_KEY") or "YOUR_OPENROUTER_API_KEY"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
# MODEL = "google/gemma-3-4b-it:free" 
MODEL = "google/gemini-3.1-flash-lite-preview" 


INPUT_FILE = "/Users/kawai_tofu/GoogleCloud/Capstone_Dev/Total_Datasets/unified_evaluation_dataset.jsonl"
OUTPUT_FILE = "test_inference_output.jsonl"
SAMPLE_SIZE = 5

async def fetch_session(session, item):
    """하나의 대화(Session) 내에서 여러 턴(Turn)을 순차적으로 처리하며 히스토리를 누적합니다."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": "http://localhost",
    }
    
    # 누적될 대화 기록
    messages = []
    if item.get("system_instruction"):
        messages.append({"role": "system", "content": item["system_instruction"]})

    # 각 턴별로 순차 요청 (대화가 이어져야 하므로 턴끼리는 비동기 병렬 처리 불가)
    for turn in item.get("turns", []):
        messages.append({"role": "user", "content": turn["user"]})
        
        payload = {
            "model": MODEL,
            "messages": messages
        }
        
        try:
            async with session.post(API_URL, headers=headers, json=payload) as response:
                result = await response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    model_output = result["choices"][0]["message"]["content"]
                else:
                    model_output = f"API Error: {result}"
                
                # 결과 기록 및 히스토리 누적
                turn["model_output"] = model_output
                messages.append({"role": "assistant", "content": model_output})
                
        except Exception as e:
            turn["model_output"] = f"Request Failed: {e}"
            break # 에러 발생 시 해당 세션 대화 중단

    return item

async def main():
    # source별로 5개씩 수집
    source_counts = {}
    test_data = []
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                source = item.get("source", "unknown")
                
                if source_counts.get(source, 0) < SAMPLE_SIZE:
                    test_data.append(item)
                    source_counts[source] = source_counts.get(source, 0) + 1
    else:
        print(f"❌ 파일을 찾을 수 없습니다: {INPUT_FILE}")
        return

    print(f"🚀 Source별 샘플 현황: {source_counts}")
    print(f"🚀 총 {len(test_data)}개의 세션에 대해 비동기 API 호출을 시작합니다...")

    # 세션(서로 다른 대화 주제) 5개는 동시에 병렬(asyncio.gather)로 실행
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_session(session, item) for item in test_data]
        results = await asyncio.gather(*tasks)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for res in results:
            f.write(json.dumps(res, ensure_ascii=False) + '\n')
            
            print("=" * 80)
            print(f"Source: {res.get('source')}")
            for i, turn in enumerate(res.get('turns', [])):
                print(f" [Turn {i+1}] User: {turn['user'][:30]}...")
                print(f"          AI  : {turn.get('model_output', '')[:50]}...")
            
    print("=" * 80)
    print(f"✅ 멀티턴 테스트 완료! 결과 저장: {OUTPUT_FILE}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())