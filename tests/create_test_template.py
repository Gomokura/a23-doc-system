import sys
sys.path.insert(0, r'D:\桌面\a23-doc-system')
from openpyxl import Workbook

# 创建带占位符的模板
wb = Workbook()
sheet = wb.active

# 表头
sheet.append(['国家/地区', '大陆', '人均GDP', '人口', '每日新增数', '死亡数'])

# 添加3行占位符
sheet.append(['{{国家1}}', '{{大陆1}}', '{{GDP1}}', '{{人口1}}', '{{新增1}}', '{{死亡1}}'])
sheet.append(['{{国家2}}', '{{大陆2}}', '{{GDP2}}', '{{人口2}}', '{{新增2}}', '{{死亡2}}'])
sheet.append(['{{国家3}}', '{{大陆3}}', '{{GDP3}}', '{{人口3}}', '{{新增3}}', '{{死亡3}}'])

output = r'D:\桌面\a23-doc-system\uploads\test_template.xlsx'
wb.save(output)
print(f'已创建测试模板: {output}')
