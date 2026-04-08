import sys
sys.path.insert(0, r'D:\桌面\a23-doc-system')
import pandas as pd

df = pd.read_excel(r'D:\桌面\a23-doc-system\uploads\ddd271d7-6021-460f-a815-0871f4de75e6.xlsx')
print('总行数:', len(df))
print('唯一国家数:', df.iloc[:, 0].nunique())
print('前20个国家:', df.iloc[:, 0].unique()[:20].tolist())

china_rows = df[df.iloc[:, 0].str.contains('China', case=False, na=False)]
print('\n包含China的行数:', len(china_rows))
if len(china_rows) > 0:
    print('China第一行数据:')
    print(china_rows.iloc[0].to_dict())
