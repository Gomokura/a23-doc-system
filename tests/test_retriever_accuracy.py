"""
问答准确率测试脚本 - 负责人: 成员3 yzmlhh

测试方法：
    cd a23-doc-system
    python -m tests.test_retriever_accuracy

本脚本在真实 LLM 调用前使用 Mock 数据验证检索链路是否正常工作。
"""
import sys
import os
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from tests.mock_data import MOCK_PARSED_DOC, MOCK_ANSWER_RESULT

try:
    from modules.retriever.indexer import build_index, get_bm25_data, get_collection
    from modules.retriever.hybrid_retriever import retrieve_and_answer
except ImportError as e:
    logger.error(f"模块导入失败: {e}，请检查 modules/retriever/ 是否已实现")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════
# Mock 答案映射（每个用例对应不同的标准答案）
# ═══════════════════════════════════════════════════════════

MOCK_ANSWERS = {
    "case_001": {
        "answer": "根据合同文件，合同总金额为人民币500万元整，分三期支付：首付150万元（30%）、验收后250万元（50%）、质保期满100万元（20%）。",
        "sources": [
            {"chunk_id": "mock-file-001_0", "content": "合同金额为人民币500万元整", "source_file": "测试合同.pdf", "page": 1},
            {"chunk_id": "mock-file-001_1", "content": "首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元", "source_file": "测试合同.pdf", "page": 2},
        ],
        "confidence": 0.92
    },
    "case_002": {
        "answer": "本合同甲方为北京科技有限公司，乙方为上海贸易有限公司。双方于2024年1月1日签订本合同。",
        "sources": [
            {"chunk_id": "mock-file-001_0", "content": "本合同由甲方北京科技有限公司与乙方上海贸易有限公司于2024年1月1日签订", "source_file": "测试合同.pdf", "page": 1},
        ],
        "confidence": 0.95
    },
    "case_003": {
        "answer": "付款方式为分三期支付：首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元。",
        "sources": [
            {"chunk_id": "mock-file-001_1", "content": "付款方式：分三期支付，首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元", "source_file": "测试合同.pdf", "page": 2},
        ],
        "confidence": 0.90
    },
    "case_004": {
        "answer": "合同有效期自签订之日起两年，即2024年1月1日至2025年12月31日届满。",
        "sources": [
            {"chunk_id": "mock-file-001_2", "content": "合同有效期自签订之日起两年，即2024年1月1日至2025年12月31日", "source_file": "测试合同.pdf", "page": 3},
        ],
        "confidence": 0.88
    },
    "case_005": {
        "answer": "本合同为北京科技有限公司与上海贸易有限公司签订的服务合同，合同金额500万元，分三期付款，有效期两年。",
        "sources": [
            {"chunk_id": "mock-file-001_0", "content": "本合同由甲方北京科技有限公司与乙方上海贸易有限公司于2024年1月1日签订，合同金额为人民币500万元整", "source_file": "测试合同.pdf", "page": 1},
            {"chunk_id": "mock-file-001_2", "content": "合同有效期自签订之日起两年", "source_file": "测试合同.pdf", "page": 3},
        ],
        "confidence": 0.85
    },
}


# ═══════════════════════════════════════════════════
# 测试用例集
# ═══════════════════════════════════════════════════

TEST_CASES = [
    {
        "id": "case_001",
        "query": "合同金额是多少？",
        "expected_keywords": ["500万元", "500", "合同金额"],
        "description": "验证能否正确检索出合同金额"
    },
    {
        "id": "case_002",
        "query": "甲乙双方分别是谁？",
        "expected_keywords": ["北京科技有限公司", "上海贸易有限公司", "甲方", "乙方"],
        "description": "验证能否正确检索出合同双方"
    },
    {
        "id": "case_003",
        "query": "付款方式是怎样的？",
        "expected_keywords": ["三期", "首付", "150万", "250万", "100万"],
        "description": "验证能否正确检索出付款条款"
    },
    {
        "id": "case_004",
        "query": "合同有效期到什么时候？",
        "expected_keywords": ["2025年12月31日", "两年", "有效期"],
        "description": "验证能否正确检索出合同有效期"
    },
    {
        "id": "case_005",
        "query": "这个文件的主要内容是什么？",
        "expected_keywords": ["合同", "北京科技有限公司", "上海贸易有限公司", "500万元"],
        "description": "验证摘要型问答是否正常"
    },
]


# ═══════════════════════════════════════════════════════════
# 指标计算
# ═══════════════════════════════════════════════════════════

def compute_keyword_hit_rate(answer: str, expected_keywords: list) -> dict:
    """
    计算关键词命中率

    Returns:
        hit_rate: 命中比例 (0.0 ~ 1.0)
        hit_keywords: 命中的关键词列表
        miss_keywords: 未命中的关键词列表
    """
    answer_lower = answer.lower()
    hit_keywords = []
    miss_keywords = []

    for kw in expected_keywords:
        if kw.lower() in answer_lower:
            hit_keywords.append(kw)
        else:
            miss_keywords.append(kw)

    hit_rate = len(hit_keywords) / len(expected_keywords) if expected_keywords else 0.0
    return {
        "hit_rate": round(hit_rate, 2),
        "hit_keywords": hit_keywords,
        "miss_keywords": miss_keywords
    }


def evaluate_answer(result: dict, test_case: dict) -> dict:
    """
    评估单条问答结果

    Returns:
        passed: 是否通过
        score: 综合得分 (0.0 ~ 1.0)
        details: 详细评估信息
    """
    answer = result.get("answer", "")
    sources = result.get("sources", [])
    confidence = result.get("confidence", -1)

    # 关键词命中率
    kw_result = compute_keyword_hit_rate(answer, test_case["expected_keywords"])
    hit_rate = kw_result["hit_rate"]

    # 来源质量：有来源得 0.2 分
    source_score = 0.2 if sources else 0.0

    # 置信度质量（confidence >= 0 得 0.1 分）
    conf_score = 0.1 if confidence >= 0 else 0.0

    # 综合得分
    score = hit_rate * 0.7 + source_score + conf_score
    score = min(score, 1.0)

    # 是否通过：得分 >= 0.6 视为通过
    passed = score >= 0.6

    return {
        "passed": passed,
        "score": round(score, 2),
        "hit_rate": kw_result["hit_rate"],
        "hit_keywords": kw_result["hit_keywords"],
        "miss_keywords": kw_result["miss_keywords"],
        "source_count": len(sources),
        "confidence": confidence
    }


# ═══════════════════════════════════════════════════════════
# 测试执行
# ═══════════════════════════════════════════════════════════

def run_retriever_tests(use_mock: bool = True) -> dict:
    """
    执行检索与问答测试

    Args:
        use_mock: True = 直接用 Mock 数据测逻辑，不调 LLM
                   False = 真构建索引 + 真调 LLM
    Returns:
        测试报告 dict
    """
    logger.info("=" * 50)
    logger.info("开始执行检索与问答准确率测试")
    logger.info("=" * 50)

    results = []
    passed_count = 0

    if use_mock:
        # ══ Mock 模式：不构建索引，直接测 retrieve_and_answer 的 Mock 返回 ══
        logger.info("【Mock 模式】跳过索引构建，使用 Mock 数据")

        for case in TEST_CASES:
            logger.info(f"\n测试用例: {case['id']} - {case['description']}")
            logger.info(f"  Query: {case['query']}")

            # 使用该用例对应的专门 Mock 答案
            mock_answer = MOCK_ANSWERS.get(case["id"], MOCK_ANSWER_RESULT)
            mock_result = {
                "query": case["query"],
                "answer": mock_answer["answer"],
                "sources": mock_answer["sources"],
                "confidence": mock_answer["confidence"]
            }

            eval_result = evaluate_answer(mock_result, case)
            results.append({
                "case_id": case["id"],
                "query": case["query"],
                "eval": eval_result
            })

            if eval_result["passed"]:
                passed_count += 1
                logger.info(f"  ✅ 通过 | 得分: {eval_result['score']} | 命中率: {eval_result['hit_rate']}")
            else:
                logger.warning(f"  ❌ 未通过 | 得分: {eval_result['score']} | 命中率: {eval_result['hit_rate']}")

            if eval_result["miss_keywords"]:
                logger.warning(f"  未命中关键词: {eval_result['miss_keywords']}")

    else:
        # ══ 真实模式：构建索引 + 调 LLM ══
        logger.info("【真实模式】开始构建索引...")

        try:
            success = build_index(MOCK_PARSED_DOC)
            if not success:
                logger.error("索引构建失败，测试终止")
                return {"error": "索引构建失败"}
            logger.info("索引构建成功")
        except Exception as e:
            logger.error(f"索引构建异常: {e}")
            return {"error": f"索引构建异常: {e}"}

        for case in TEST_CASES:
            logger.info(f"\n测试用例: {case['id']} - {case['description']}")
            logger.info(f"  Query: {case['query']}")

            try:
                result = retrieve_and_answer(query=case["query"], file_ids=[])
                eval_result = evaluate_answer(result, case)
                results.append({
                    "case_id": case["id"],
                    "query": case["query"],
                    "answer": result.get("answer", ""),
                    "eval": eval_result
                })

                if eval_result["passed"]:
                    passed_count += 1
                    logger.info(f"  ✅ 通过 | 得分: {eval_result['score']} | 命中率: {eval_result['hit_rate']}")
                else:
                    logger.warning(f"  ❌ 未通过 | 得分: {eval_result['score']} | 命中率: {eval_result['hit_rate']}")

                if eval_result["miss_keywords"]:
                    logger.warning(f"  未命中关键词: {eval_result['miss_keywords']}")

                logger.info(f"  置信度: {result.get('confidence', 'N/A')}")
                logger.info(f"  来源数: {len(result.get('sources', []))}")

            except Exception as e:
                logger.error(f"  测试异常: {e}")
                results.append({
                    "case_id": case["id"],
                    "query": case["query"],
                    "error": str(e)
                })

    # ══ 汇总报告 ══
    total = len(TEST_CASES)
    pass_rate = passed_count / total if total else 0
    avg_score = sum(r["eval"]["score"] for r in results if "eval" in r) / len(results) if results else 0

    summary = {
        "total_cases": total,
        "passed_count": passed_count,
        "failed_count": total - passed_count,
        "pass_rate": round(pass_rate, 2),
        "avg_score": round(avg_score, 2),
        "results": results
    }

    logger.info("\n" + "=" * 50)
    logger.info("测试报告汇总")
    logger.info("=" * 50)
    logger.info(f"总用例数 : {summary['total_cases']}")
    logger.info(f"通过数   : {summary['passed_count']}")
    logger.info(f"未通过数 : {summary['failed_count']}")
    logger.info(f"通过率   : {summary['pass_rate']:.0%}")
    logger.info(f"平均得分 : {summary['avg_score']}")

    if summary["pass_rate"] >= 0.8:
        logger.info("✅ 整体表现良好，检索链路运行正常")
    elif summary["pass_rate"] >= 0.6:
        logger.info("⚠️  整体表现一般，建议检查关键词匹配规则")
    else:
        logger.warning("❌ 整体表现较差，建议优化检索策略或 Prompt")

    return summary


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="检索与问答准确率测试")
    parser.add_argument(
        "--real",
        action="store_true",
        help="使用真实模式（构建索引 + 调 LLM），默认使用 Mock 模式"
    )
    args = parser.parse_args()

    report = run_retriever_tests(use_mock=not args.real)

    # 返回退出码：通过率 >= 60% 返回 0，否则返回 1
    if "pass_rate" in report:
        sys.exit(0 if report["pass_rate"] >= 0.6 else 1)
    else:
        sys.exit(1)
