import asyncio
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

async def test_inference():
    api_url = os.getenv("VLLM_API_URL")
    model = os.getenv("EVAL_MODEL_NAME")
    api_key = "dummy_token"
    
    print(f"Testing vLLM Inference...")
    print(f"URL: {api_url}")
    print(f"Model: {model}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "안녕하세요, 간단한 자기소개 부탁드립니다."}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(api_url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    response_text = result["choices"][0]["message"]["content"]
                    print("\n[Inference Result]")
                    print(response_text)
                else:
                    print(f"\n[Error] Status Code: {resp.status}")
                    print(await resp.text())
        except Exception as e:
            print(f"\n[Exception] {e}")

if __name__ == "__main__":
    asyncio.run(test_inference())
