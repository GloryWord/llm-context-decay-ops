import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# 1. 데이터 로드
file_path = "/Users/kawai_tofu/Desktop/서울과학기술대학교_로컬/캡스톤디자인/capstone_dev/2026/final_evaluation_results.jsonl"
data_list = []

if not os.path.exists(file_path):
    print(f"파일을 찾을 수 없습니다: {file_path}")
else:
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            cumulative_context = len(item.get("system_instruction", ""))
            
            for i, turn in enumerate(item["turns"]):
                user_input = turn.get("user", "")
                model_output = turn.get("model_output", "")
                
                data_list.append({
                    "Source": item.get("source", "Unknown"),
                    "Turn": i + 1,
                    "Context Length": cumulative_context + len(user_input),
                    "Judge Score": float(turn.get("judge_score", 0)),
                    "IFS": turn.get("current_ifs", 0)
                })
                cumulative_context += len(user_input) + len(model_output)

    df = pd.DataFrame(data_list)

    # --- [핵심] 2. 이상치 강제 클램핑 (1.0 ~ 5.0) ---
    # DataFrame 전체 레벨에서 적용하여 누락을 방지합니다.
    df['Judge Score'] = df['Judge Score'].clip(1.0, 5.0)
    
    # 제대로 적용되었는지 콘솔에서 확인
    print(f"Score Range: {df['Judge Score'].min()} ~ {df['Judge Score'].max()}")

    # 3. 시각화 설정
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # [차트 1] Turn vs Judge Score (Y축 범위 고정)
    sns.lineplot(ax=axes[0, 0], data=df, x="Turn", y="Judge Score", marker="o", errorbar="sd")
    axes[0, 0].set_ylim(0.5, 5.5) # 범위를 5.5로 고정하여 이상치 유무 즉시 확인 가능
    axes[0, 0].set_title("Average Judge Score by Turn (Clamped)")

    # [차트 2] Turn vs IFS
    sns.lineplot(ax=axes[0, 1], data=df, x="Turn", y="IFS", marker="s", color="orange", errorbar="sd")
    axes[0, 1].set_title("Average IFS by Turn")

    # [차트 3] Context Length vs Judge Score
    sns.regplot(ax=axes[1, 0], data=df, x="Context Length", y="Judge Score", 
                scatter_kws={'alpha':0.3}, line_kws={'color':'red'})
    axes[1, 0].set_ylim(0.5, 5.5)
    axes[1, 0].set_title("Judge Score vs Context Length")

    # [차트 4] Context Length vs IFS
    sns.regplot(ax=axes[1, 1], data=df, x="Context Length", y="IFS", 
                scatter_kws={'alpha':0.3, 'color':'orange'}, line_kws={'color':'blue'})
    axes[1, 1].set_title("IFS vs Context Length")

    plt.suptitle("LLM Evaluation Analysis: Outliers Clamped (1.0 - 5.0)", fontsize=16)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    # plt.show()
    
    # 결과 저장 또는 출력
    plt.savefig("evaluation_analysis.png")