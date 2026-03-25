"""
RAG 评估测试 - 负责人: 成员3
评估 RAG 系统四大核心指标

使用方式：
    python -m tests.test_rag_evaluation
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from tests.rag_evaluator import RAGEvaluator, batch_evaluate


# ═══════════════════════════════════════════════════════════
# 评估测试用例
# ═══════════════════════════════════════════════════════════

EVAL_CASES = [
    {
        "id": "eval_001",
        "query": "合同金额是多少？",
        "answer": "根据合同文件，合同总金额为人民币500万元整，分三期支付。",
        "contexts": [
            "本合同由甲方北京科技有限公司与乙方上海贸易有限公司于2024年1月1日签订，合同金额为人民币500万元整。",
            "付款方式：分三期支付，首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元。"
        ],
        "ground_truth": "合同金额为500万元"
    },
    {
        "id": "eval_002",
        "query": "甲乙双方分别是谁？",
        "answer": "本合同甲方为北京科技有限公司，乙方为上海贸易有限公司。",
        "contexts": [
            "本合同由甲方北京科技有限公司与乙方上海贸易有限公司于2024年1月1日签订，合同金额为人民币500万元整。"
        ],
        "ground_truth": "甲方：北京科技有限公司，乙方：上海贸易有限公司"
    },
    {
        "id": "eval_003",
        "query": "付款方式是怎样的？",
        "answer": "付款方式为分三期支付：首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元。",
        "contexts": [
            "付款方式：分三期支付，首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元。"
        ],
        "ground_truth": "分三期：首付150万，验收后250万，质保期满100万"
    },
    {
        "id": "eval_004",
        "query": "合同有效期到什么时候？",
        "answer": "合同有效期自签订之日起两年，即2024年1月1日至2025年12月31日届满。",
        "contexts": [
            "合同有效期自签订之日起两年，即2024年1月1日至2025年12月31日。"
        ],
        "ground_truth": "有效期两年，2025年12月31日届满"
    },
    {
        "id": "eval_005",
        "query": "这个文件的主要内容是什么？",
        "answer": "本合同为北京科技有限公司与上海贸易有限公司签订的服务合同，合同金额500万元，分三期付款，有效期两年。",
        "contexts": [
            "本合同由甲方北京科技有限公司与乙方上海贸易有限公司于2024年1月1日签订，合同金额为人民币500万元整。",
            "付款方式：分三期支付，首付30%即150万元，验收后付50%即250万元，质保期满付尾款20%即100万元。",
            "合同有效期自签订之日起两年，即2024年1月1日至2025年12月31日。"
        ],
        "ground_truth": "北京科技与上海贸易签订500万元服务合同"
    },
]


def run_evaluation():
    """执行 RAG 评估测试"""
    logger.info("=" * 60)
    logger.info("开始执行 RAG 系统评估测试")
    logger.info("=" * 60)

    evaluator = RAGEvaluator()

    for case in EVAL_CASES:
        logger.info(f"\n{'='*50}")
        logger.info(f"测试用例: {case['id']}")
        logger.info(f"Query: {case['query']}")
        logger.info("-" * 50)

        result = evaluator.evaluate(
            query=case["query"],
            answer=case["answer"],
            contexts=case["contexts"],
            ground_truth=case.get("ground_truth")
        )

        logger.info(f"\n{result.summary()}")

    # 批量评估汇总
    logger.info("\n" + "=" * 60)
    logger.info("批量评估汇总报告")
    logger.info("=" * 60)

    report = batch_evaluate(EVAL_CASES)

    logger.info(f"总用例数 : {report['total_cases']}")
    logger.info(f"通过数   : {report['passed']}")
    logger.info(f"未通过数 : {report['failed']}")
    logger.info(f"通过率   : {report['pass_rate']:.0%}")

    logger.info("\n平均得分：")
    avg = report["avg_scores"]
    logger.info(f"  忠实度 (Faithfulness)     : {avg['faithfulness']:.3f}")
    logger.info(f"  答案相关性 (Answer Relev.) : {avg['answer_relevancy']:.3f}")
    logger.info(f"  上下文精确度 (Ctx Precis.) : {avg['context_precision']:.3f}")
    logger.info(f"  上下文召回率 (Ctx Recall)   : {avg['context_recall']:.3f}")
    logger.info(f"  综合得分 (Overall)         : {avg['overall']:.3f}")

    if report["pass_rate"] >= 0.8:
        logger.info("\n✅ RAG 系统评估表现优秀")
    elif report["pass_rate"] >= 0.6:
        logger.info("\n⚠️ RAG 系统评估表现一般，建议优化")
    else:
        logger.warning("\n❌ RAG 系统评估表现较差，需要改进")

    return report


if __name__ == "__main__":
    report = run_evaluation()

    # 返回退出码：通过率 >= 60% 返回 0，否则返回 1
    sys.exit(0 if report["pass_rate"] >= 0.6 else 1)
