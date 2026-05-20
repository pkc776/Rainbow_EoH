import json
import argparse
import sys

def evaluate_json_programs(file_path):
    # 1. 讀取 JSON 檔案
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            programs = json.load(f)
    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {file_path}")
        return
    except json.JSONDecodeError:
        print(f"錯誤：{file_path} 不是有效的 JSON 格式")
        return

    # 2. 逐一評估每個 program
    for i, item in enumerate(programs):
        code_content = item.get("code", "")
        algorithm_name = item.get("algorithm", "Unknown")
        
        print(f"--- 正在評估第 {i+1} 個演算法: {algorithm_name[:50]}... ---")

        # 建立獨立的命名空間，避免不同 program 之間的變數污染
        namespace = {}
        
        try:
            # 執行程式碼以定義函數（例如定義出 heuristic）
            exec(code_content, namespace)
            
            # 取得剛剛定義的 heuristic 函數
            heuristic_func = namespace.get("heuristic")
            
            if callable(heuristic_func):
                # 假設我們要測試 n=100
                test_n = 1094
                result = heuristic_func(test_n, rng=42)
                
                print(f"執行成功！結果長度: {len(result)}")
                # print(f"結果範例: {list(result)[:10]}") # 若想看結果可取消註解
            else:
                print("跳過：程式碼中找不到名為 'heuristic' 的可執行函數")

        except Exception as e:
            print(f"執行第 {i+1} 個程式碼時出錯: {e}")
        
        print("\n")

if __name__ == "__main__":
    # 使用 argparse 接收命令列參數
    parser = argparse.ArgumentParser(description="從 JSON 評估多個 Python 程式")
    parser.add_argument("filename", help="JSON 檔案的名稱")
    
    args = parser.parse_args()
    
    evaluate_json_programs(args.filename)