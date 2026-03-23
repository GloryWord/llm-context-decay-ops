import json
import ast
import os

def expand_and_format_json(input_path, output_path="expanded_pretty_data.json"):
    if not os.path.exists(input_path):
        print(f"❌ 오류: '{input_path}' 파일을 찾을 수 없습니다.")
        return

    try:
        # 1. 메인 JSON 파일 로드
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2. 'turns' 리스트 순회 및 내부 데이터 정제
        if "turns" in data:
            for turn in data["turns"]:
                
                # [수정된 부분] "user" 텍스트를 여러 줄의 리스트로 분리
                if "user" in turn and isinstance(turn["user"], str):
                    # \n을 기준으로 문자열을 잘라 리스트로 만듭니다.
                    turn["user"] = turn["user"].split('\n')
                
                # "target" 문자열을 딕셔너리로 변환
                if "target" in turn and isinstance(turn["target"], str):
                    try:
                        turn["target"] = ast.literal_eval(turn["target"])
                    except (ValueError, SyntaxError):
                        pass

        # 3. 최종 데이터를 들여쓰기 포함하여 저장
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"✅ 성공! 중첩 내용과 긴 텍스트를 모두 풀어서 '{output_path}'에 저장했습니다.")

    except Exception as e:
        print(f"❌ 처리 중 오류 발생: {e}")

# 실행
expand_and_format_json("raw_data.txt", "pretty_data.json")