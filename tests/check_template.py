import sys
sys.path.insert(0, r'D:\桌面\a23-doc-system')
import pandas as pd

template_path = r'D:\桌面\a23-doc-system\uploads\69eb3c13-8fdc-4e12-a461-92da0b1c5dbf.xlsx'
df = pd.read_excel(template_path)
print('模板行数:', len(df))
print('模板列数:', len(df.columns))
print('\n模板内容预览:')
print(df.head(10).to_string())
