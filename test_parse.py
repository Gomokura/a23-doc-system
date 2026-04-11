"""检查文档实际段落结构"""
import sys
sys.path.insert(0, '.')

from docx import Document
import re

# 检查所有上传的 docx 文件
import os
upload_dir = "uploads"

for fname in sorted(os.listdir(upload_dir)):
    if not fname.endswith('.docx'):
        continue
    path = os.path.join(upload_dir, fname)
    doc = Document(path)

    print(f"\n{'='*60}")
    print(f"文件: {fname}")
    print(f"{'='*60}")

    body_count = 0
    heading_count = 0
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name if p.style else 'Normal'
        is_heading = bool(re.search(r'标题|heading', style, re.I))
        if is_heading:
            heading_count += 1
            prefix = f"[标题{heading_count}]"
        else:
            body_count += 1
            prefix = f"[正文{body_count}]"

        preview = text[:40] + ('...' if len(text) > 40 else '')
        print(f"  doc_idx={i}  {prefix}  style='{style}'  text='{preview}'")
