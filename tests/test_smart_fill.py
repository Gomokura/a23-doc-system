"""直接测试智能回填核心逻辑"""
import sys
sys.path.insert(0, r'D:\桌面\a23-doc-system')

from modules.filler.intelligent_filler import extract_and_fill

template_path = r'D:\桌面\a23-doc-system\uploads\69eb3c13-8fdc-4e12-a461-92da0b1c5dbf.xlsx'
source_file_ids = ['ddd271d7-6021-460f-a815-0871f4de75e6']
output_path = r'D:\桌面\a23-doc-system\outputs\smart_filled.xlsx'

print("开始智能回填（LLM自动识别表头并提取数据）...")
success = extract_and_fill(template_path, source_file_ids, output_path, max_rows=5)

if success:
    import pandas as pd
    df = pd.read_excel(output_path)
    print(f"\n智能回填成功！共 {len(df)} 行数据：")
    print(df.to_string(index=False))
else:
    print("\n智能回填失败")
