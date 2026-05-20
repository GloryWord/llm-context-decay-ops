import asyncio
import os
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.http_headers import build_json_headers

load_dotenv(ROOT / ".env")

async def test_inference():
    api_url = os.getenv("VLLM_API_URL")
    model = os.getenv("EVAL_MODEL_NAME")
    api_key = os.getenv("VLLM_API_KEY", "")
    
    print(f"Testing vLLM Inference...")
    print(f"URL: {api_url}")
    print(f"Model: {model}")
    
    headers = build_json_headers(api_url, api_key)
    
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
