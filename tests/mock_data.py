"""
标准 Mock 数据 - 负责人: 成员1
所有成员在对接真实模块前，统一使用此文件中的 Mock 数据
禁止各自随意造测试数据，格式必须与此文件保持一致

使用方式:
    from tests.mock_data import MOCK_PARSED_DOC, MOCK_ANSWER_RESULT
"""

# ── Mock ParsedDocument（成员3、4、5开发期间使用）──────────────
MOCK_PARSED_DOC = {
    "file_id": "mock-file-001",
    "filename": "测试合同.pdf",
    "file_type": "pdf",
    "chunks": [
        {
            "chunk_id": "mock-file-001_0",
            "content": "本合同由甲方北京科技有限公司与乙方上海贸易有限公司于2024年1月1日签订，合同金额为人民币500万元整。",
            "page": 1,
            "chunk_type": "text",
            "metadata": {}
        },
        {
            "chunk_id": "mock-file-001_1",
            "content": "付款方式：分三期支付，首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元。",
            "page": 2,
            "chunk_type": "text",
            "metadata": {}
        },
        {
            "chunk_id": "mock-file-001_2",
            "content": "合同有效期自签订之日起两年，即2024年1月1日至2025年12月31日。",
            "page": 3,
            "chunk_type": "text",
            "metadata": {}
        },
    ],
    "entities": [
        {"key": "合同金额",  "value": "500万元",         "source_chunk_id": "mock-file-001_0"},
        {"key": "甲方",      "value": "北京科技有限公司", "source_chunk_id": "mock-file-001_0"},
        {"key": "乙方",      "value": "上海贸易有限公司", "source_chunk_id": "mock-file-001_0"},
        {"key": "签订日期",  "value": "2024年1月1日",    "source_chunk_id": "mock-file-001_0"},
        {"key": "合同有效期","value": "两年",             "source_chunk_id": "mock-file-001_2"},
    ],
    "summary": "北京科技有限公司与上海贸易有限公司签订的500万元服务合同，分三期付款，有效期两年。"
}

# ── Mock RetrievalResult（成员3内部使用）──────────────────────
MOCK_RETRIEVAL_RESULT = {
    "query": "合同金额是多少？",
    "chunks": [
        {
            "chunk_id":    "mock-file-001_0",
            "content":     "合同金额为人民币500万元整",
            "score":       0.95,
            "source_file": "测试合同.pdf",
            "page":        1,
        },
        {
            "chunk_id":    "mock-file-001_1",
            "content":     "首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元",
            "score":       0.87,
            "source_file": "测试合同.pdf",
            "page":        2,
        },
    ]
}

# ── Mock AnswerResult（成员4、5开发期间使用）──────────────────
MOCK_ANSWER_RESULT = {
    "query": "合同金额是多少？",
    "answer": "根据合同文件，合同总金额为人民币500万元整，分三期支付：首付150万元（30%）、验收后250万元（50%）、质保期满100万元（20%）。",
    "sources": [
        {
            "chunk_id":    "mock-file-001_0",
            "content":     "合同金额为人民币500万元整",
            "source_file": "测试合同.pdf",
            "page":        1,
        },
        {
            "chunk_id":    "mock-file-001_1",
            "content":     "首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元",
            "source_file": "测试合同.pdf",
            "page":        2,
        },
    ],
    "confidence": 0.92
}

# ── Mock FillRequest（成员4测试用）────────────────────────────
MOCK_FILL_REQUEST = {
    "template_file_id": "mock-template-001",
    "answers": [
        {"field_name": "合同金额",  "value": "500万元",         "source_chunk_id": "mock-file-001_0"},
        {"field_name": "甲方名称",  "value": "北京科技有限公司", "source_chunk_id": "mock-file-001_0"},
        {"field_name": "乙方名称",  "value": "上海贸易有限公司", "source_chunk_id": "mock-file-001_0"},
        {"field_name": "签订日期",  "value": "2024年1月1日",    "source_chunk_id": "mock-file-001_0"},
    ]
}
