import sys
sys.path.insert(0, r'D:\桌面\a23-doc-system')
import pandas as pd

output_path = r'D:\桌面\a23-doc-system\outputs\02088079-0685-494c-bec7-63a30321ced2.xlsx'
df = pd.read_excel(output_path)
print('回填后的文件内容:')
print(df.to_string())
