# src/ 소스 코드 개요

## 모듈 구성
```
src/
├── data_pipeline/   ← 데이터 로딩 및 전처리
├── evaluation/      ← 평가 지표 계산
├── models/          ← API 호출 및 프롬프트
└── utils/           ← 공통 유틸리티
```

각 하위 디렉토리에 별도 CLAUDE.md 있음 (해당 디렉토리 접근 시 로드).

## 모듈 간 의존성
```
data_pipeline ──→ models ──→ evaluation
     ↓                           ↓
   utils  ←──────────────────── utils
```

## 공통 데이터 스키마

### 입력 레코드 (processed)
```python
{
    "id": str,           # 고유 식별자
    "question": str,     # 문제 텍스트
    "answer": str,       # 정답
    "category": str,     # 문제 유형
    "difficulty": int    # 난이도 (1-5)
}
```

### 출력 레코드 (outputs)
```python
{
    "id": str,
    "model": str,        # 모델 식별자
    "prompt": str,       # 실제 입력 프롬프트
    "response": str,     # 모델 응답
    "latency_ms": float,
    "tokens_used": int,
    "timestamp": str     # ISO 8601
}
```