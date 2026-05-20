# import pandas as pd
# import numpy as np
# import json

# def process_summary_csv(file_path):
#     df = pd.read_csv(file_path)
    
#     # 找出所有以 __len 結尾的欄位
#     len_cols = [c for c in df.columns if c.endswith('__len')]
    
#     big_maps = {}
#     proximity_stats = {}

#     for col in len_cols:
#         # 去掉 __len 得到原始名稱
#         clean_name = col.replace('__len', '')
        
#         # 定義判定 optimal 值的邏輯
#         def get_optimal(row):
#             if row['bound_type'] == 'range':
#                 return row['opt_low']
#             elif row['bound_type'] == 'exact':
#                 return row['opt_high']
#             else:
#                 return np.nan

#         # 計算該 row 的 optimal 值
#         temp_df = df.copy()
#         temp_df['optimal'] = temp_df.apply(get_optimal, axis=1)
        
#         # 只取有值的 row (optimal 與 該欄位皆非空值)
#         valid_mask = temp_df['optimal'].notna() & temp_df[col].notna()
#         subset = temp_df[valid_mask]
        
#         # 建立 {n: (val - optimal)} 的 map
#         diff_map = {
#             int(row['n']): float(row[col] - row['optimal']) 
#             for _, row in subset.iterrows()
#         }
#         big_maps[clean_name] = diff_map
        
#         # 統計與 optimal 的距離 (使用平均絕對誤差 MAE)
#         if not subset.empty:
#             avg_abs_diff = (subset[col] - subset['optimal']).abs().mean()
#             proximity_stats[clean_name] = avg_abs_diff

#     # 排序統計結果 (由近到遠)
#     sorted_stats = sorted(proximity_stats.items(), key=lambda x: x[1])
    
#     return big_maps, sorted_stats

# # 執行運算
# maps, stats = process_summary_csv('summary-11.csv')

# # 印出統計結果
# print("--- 欄位與 Optimal 值接近程度 (平均絕對誤差) ---")
# for name, score in stats:
#     print(f"{name}: {score:.4f}")

# closest = stats[0][0] if stats else "None"
# print(f"\n最接近 Optimal 的欄位是: {closest}")

# # 將詳細的 big maps 存入 JSON
# with open('column_diff_maps.json', 'w') as f:
#     json.dump(maps, f)

import pandas as pd
import numpy as np
import json

def process_data_with_extended_rules(file_path):
    df = pd.read_csv(file_path)
    
    # 找出所有以 __len 結尾的欄位
    len_cols = [c for c in df.columns if c.endswith('__len')]
    
    big_maps = {}
    proximity_stats = {}

    # 定義更新後的判定邏輯
    def get_target_val(row):
        # 1. 如果 bound_type 是 range -> 用 opt_low
        if row['bound_type'] == 'range':
            return row['opt_low']
        # 2. 如果 bound_type 是 exact -> 用 opt_high
        elif row['bound_type'] == 'exact':
            return row['opt_high']
        # 3. 補充規則：如果 n > 250 且 opt_low 有值 -> 用 opt_low
        elif row['n'] > 250 and pd.notna(row['opt_low']):
            return row['opt_low']
        else:
            return np.nan

    # 預先計算每一列的目標基準值
    df['target_optimal'] = df.apply(get_target_val, axis=1)

    for col in len_cols:
        # 去除 __len 字樣作為 Map 的 Key
        clean_name = col.replace('__len', '')
        
        # 篩選出基準值與該欄位皆有資料的 rows
        valid_df = df[df['target_optimal'].notna() & df[col].notna()]
        
        # 建立 {n: 差值} 的 Map
        # 差值 = 欄位值 - 基準值
        diff_map = {
            int(row['n']): float(row[col] - row['target_optimal']) 
            for _, row in valid_df.iterrows()
        }
        big_maps[clean_name] = diff_map
        
        # 計算平均絕對誤差 (MAE) 來衡量「最近」程度
        if not valid_df.empty:
            mae = (valid_df[col] - valid_df['target_optimal']).abs().mean()
            proximity_stats[clean_name] = mae

    # 依照誤差由小到大排序
    sorted_stats = sorted(proximity_stats.items(), key=lambda x: x[1])
    
    return big_maps, sorted_stats

# 執行分析
final_maps, final_stats = process_data_with_extended_rules('summary-11.csv')

# 輸出最接近的前 5 名
print("--- 欄位接近程度排行 (平均絕對誤差，愈小愈準) ---")
for name, error in final_stats:
    print(f"{name}: {error:.4f}")

# 儲存 Big Map 到 JSON 檔案
with open('diff_maps_v2.json', 'w') as f:
    json.dump(final_maps, f)