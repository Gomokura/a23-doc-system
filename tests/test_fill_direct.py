import sys
sys.path.insert(0, r'D:\桌面\a23-doc-system')
from modules.filler.table_filler import fill_table

template_path = r'D:\桌面\a23-doc-system\uploads\test_template.xlsx'
output_path = r'D:\桌面\a23-doc-system\outputs\test_filled.xlsx'

fill_request = {
    "template_file_id": "test",
    "answers": [
        {"field_name": "国家1", "value": "Albania"},
        {"field_name": "大陆1", "value": "Europe"},
        {"field_name": "GDP1", "value": "5353.2"},
        {"field_name": "人口1", "value": "2873457"},
        {"field_name": "新增1", "value": "0"},
        {"field_name": "死亡1", "value": "0"},
        {"field_name": "国家2", "value": "Austria"},
        {"field_name": "大陆2", "value": "Europe"},
        {"field_name": "GDP2", "value": "50277.0"},
        {"field_name": "人口2", "value": "9006398"},
        {"field_name": "新增2", "value": "5"},
        {"field_name": "死亡2", "value": "0"},
    ]
}

success = fill_table(template_path, fill_request, output_path)
print(f'回填结果: {"成功" if success else "失败"}')

if success:
    import pandas as pd
    df = pd.read_excel(output_path)
    print('\n回填后的内容:')
    print(df.to_string())
