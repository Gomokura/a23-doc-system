"""
RAG 评估框架 - 负责人: 成员3
基于 RAGAS 理念实现的本地评估模块

评估指标：
1. Faithfulness（忠实度）：答案是否忠实于检索到的上下文
2. Answer Relevancy（答案相关性）：答案与问题的相关程度
3. Context Precision（上下文精确度）：检索结果与问题的相关程度
4. Context Recall（上下文召回率）：检索结果是否覆盖答案所需信息

使用方式：
    from tests.rag_evaluator import RAGEvaluator, EvaluationResult

    evaluator = RAGEvaluator()
    result = evaluator.evaluate(
        query="合同金额是多少？",
        answer="合同金额为500万元",
        contexts=["本合同金额为人民币500万元整"],
        ground_truth="合同金额为500万元"
    )
"""
from dataclasses import dataclass
from typing import List, Optional
import re
import math

from loguru import logger


@dataclass
class EvaluationResult:
    """评估结果数据类"""
    query: str
    answer: str

    # 各维度得分 (0.0 ~ 1.0)
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0

    # 综合得分
    overall_score: float = 0.0

    # 详细分析
    details: dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        # 计算综合得分（加权平均）
        self.overall_score = round(
            self.faithfulness * 0.25 +
            self.answer_relevancy * 0.25 +
            self.context_precision * 0.25 +
            self.context_recall * 0.25,
            3
        )

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "answer": self.answer,
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "overall_score": self.overall_score,
            "details": self.details
        }

    def summary(self) -> str:
        """生成简要报告"""
        status = "✅ 通过" if self.overall_score >= 0.6 else "❌ 未通过"
        return (
            f"{status} | "
            f"综合:{self.overall_score:.2f} | "
            f"忠实:{self.faithfulness:.2f} | "
            f"相关:{self.answer_relevancy:.2f} | "
            f"精确:{self.context_precision:.2f} | "
            f"召回:{self.context_recall:.2f}"
        )


class RAGEvaluator:
    """
    RAG 系统评估器

    实现思路：
    - Faithfulness：通过检查答案中的事实陈述是否能在上下文中找到
    - Answer Relevancy：通过计算答案与问题的关键词重叠度
    - Context Precision：通过计算上下文与问题的相似度
    - Context Recall：通过检查上下文是否包含答案的关键信息
    """

    def __init__(self):
        self.name = "RAG-Evaluator"
        logger.info(f"{self.name} 初始化完成")

    def _extract_facts(self, text: str) -> List[str]:
        """从文本中提取事实陈述（简单规则）"""
        # 去除标点，分割句子
        sentences = re.split(r'[。！？\n]', text)
        facts = [s.strip() for s in sentences if len(s.strip()) > 5]
        return facts

    def _compute_keyword_overlap(self, text1: str, text2: str) -> float:
        """计算两个文本的关键词重叠度"""
        # 简单分词（按字符级别，保留中文词）
        def tokenize(text):
            # 去除标点，提取中文词
            text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
            tokens = [t.strip() for t in text.split() if len(t.strip()) >= 2]
            return set(tokens)

        tokens1 = tokenize(text1)
        tokens2 = tokenize(text2)

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        # Jaccard 相似度
        return len(intersection) / len(union) if union else 0.0

    def _compute_ngram_overlap(self, text1: str, text2: str, n: int = 2) -> float:
        """计算 n-gram 重叠度"""
        def get_ngrams(text, n):
            text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)
            if len(text) < n:
                return set()
            return set(text[i:i+n] for i in range(len(text) - n + 1))

        ngrams1 = get_ngrams(text1, n)
        ngrams2 = get_ngrams(text2, n)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2

        return len(intersection) / len(union) if union else 0.0

    def evaluate_faithfulness(
        self,
        answer: str,
        contexts: List[str]
    ) -> tuple:
        """
        评估答案忠实度：答案中的事实是否都能在上下文中找到

        Returns:
            (score, details): 得分和详细分析
        """
        if not answer or not contexts:
            return 0.0, {"reason": "答案或上下文为空"}

        # 合并上下文
        combined_context = " ".join(contexts)

        # 提取答案中的事实
        facts = self._extract_facts(answer)
        if not facts:
            return 1.0, {"reason": "答案中无事实陈述"}

        # 检查每个事实是否能在上下文中找到（部分匹配）
        supported_facts = 0
        missing_facts = []

        for fact in facts:
            # 检查事实关键词是否在上下文中
            keywords = re.findall(r'[\u4e00-\u9fa5]{2,}|[0-9]+', fact)
            matched = sum(1 for kw in keywords if kw in combined_context)
            ratio = matched / len(keywords) if keywords else 0

            if ratio >= 0.5:  # 超过一半关键词匹配
                supported_facts += 1
            else:
                missing_facts.append(fact)

        score = supported_facts / len(facts) if facts else 0.0

        details = {
            "total_facts": len(facts),
            "supported_facts": supported_facts,
            "missing_facts": missing_facts
        }

        return round(score, 3), details

    def evaluate_answer_relevancy(
        self,
        query: str,
        answer: str
    ) -> tuple:
        """
        评估答案相关性：答案是否与问题相关

        评估策略：
        1. 检查答案中是否包含问题所需的关键信息类型（数字、日期、实体名等）
        2. 检查答案长度是否合理（不是敷衍的"无法回答"）
        3. 计算 n-gram 重叠度作为辅助参考

        Returns:
            (score, details): 得分和详细分析
        """
        if not query or not answer:
            return 0.0, {"reason": "问题或答案为空"}

        # 检查是否包含敷衍性的回答
        low_effort_patterns = ["无法回答", "不知道", "没有相关", "未提及", "不清楚"]
        is_low_effort = any(p in answer for p in low_effort_patterns)
        if is_low_effort:
            return 0.0, {"reason": "敷衍性回答"}

        # 检查答案长度（过短可能是敷衍）
        if len(answer) < 5:
            return 0.0, {"reason": "答案过短"}

        # 方法1：关键词重叠
        kw_score = self._compute_keyword_overlap(query, answer)

        # 方法2：n-gram 重叠
        ngram_score = self._compute_ngram_overlap(query, answer, n=2)

        # 方法3：检查答案是否包含有意义的实体（数字、公司名等）
        entity_score = 0.0
        # 提取答案中的关键实体
        answer_entities = re.findall(r'[\u4e00-\u9fa5]{3,20}|[0-9]+\.?\d*[万千百亿]*|[a-zA-Z]+', answer)
        # 过滤常见无意义词
        stopwords = {'的', '是', '在', '有', '和', '与', '及', '或', '等', '于', '了', '为', '对', '这', '那', '个'}
        answer_entities = [e for e in answer_entities if e not in stopwords and len(e) >= 2]
        if answer_entities:
            entity_score = min(len(answer_entities) / 3, 1.0)  # 有3个以上实体得满分

        # 综合得分：实体分权重更高
        score = (kw_score * 0.3 + ngram_score * 0.2 + entity_score * 0.5)

        details = {
            "keyword_overlap": kw_score,
            "ngram_overlap": ngram_score,
            "entity_score": entity_score,
            "entities_found": answer_entities
        }

        return round(min(score, 1.0), 3), details

    def evaluate_context_precision(
        self,
        query: str,
        contexts: List[str]
    ) -> tuple:
        """
        评估上下文精确度：检索到的上下文是否与问题相关

        对于文档问答场景，问句和上下文的表述往往不同
        （问"金额" vs 文档"合同金额为..."）
        因此使用宽松匹配：检查上下文是否涉及问句的主题

        Returns:
            (score, details): 得分和详细分析
        """
        if not query or not contexts:
            return 0.0, {"reason": "问题或上下文为空"}

        combined_context = " ".join(contexts)
        if len(combined_context) < 10:
            return 0.0, {"reason": "上下文内容过短"}

        # 提取问句中的关键词
        words = re.findall(r'[\u4e00-\u9fa5]{2,8}', query)
        question_only = {'什么', '多少', '怎样', '如何', '为什么', '哪个', '哪些',
                        '什么时候', '哪里', '谁', '几个', '怎么样', '是否', '能否'}
        keywords = [w for w in words if w not in question_only]

        # 检查上下文是否涉及问句的主题
        matched_keywords = [kw for kw in keywords if kw in combined_context]
        keyword_match_rate = len(matched_keywords) / len(keywords) if keywords else 0

        # 如果有直接关键词匹配，给高分
        if keyword_match_rate >= 0.5:
            precision = keyword_match_rate
        else:
            # 宽松匹配：检查上下文是否包含文档特征词（表示上下文是有意义的）
            doc_features = ['签订', '合同', '协议', '公司', '付款', '有效', '签订日期',
                          '金额', '日期', '期限', '服务', '甲方', '乙方', '人民币', '万元']
            matched_features = [f for f in doc_features if f in combined_context]

            # 有文档特征词，说明上下文是相关的
            if matched_features:
                # 基于特征词数量给分（越多表示越相关）
                precision = min(0.6 + len(matched_features) * 0.05, 0.95)
            else:
                precision = 0.0

        details = {
            "precision": precision,
            "keywords": keywords,
            "matched_keywords": matched_keywords,
            "keyword_match_rate": keyword_match_rate
        }

        return round(precision, 3), details

    def evaluate_context_recall(
        self,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> tuple:
        """
        评估上下文召回率：上下文是否覆盖了答案所需的关键信息

        Args:
            answer: LLM 生成的答案
            contexts: 检索到的上下文
            ground_truth: 标准答案（如果有）

        Returns:
            (score, details): 得分和详细分析
        """
        if not answer:
            return 0.0, {"reason": "答案为空"}

        # 使用 ground_truth 或 answer 作为参考
        reference = ground_truth if ground_truth else answer
        combined_context = " ".join(contexts) if contexts else ""

        # 提取关键实体（数字、公司名、日期等）
        key_entities = []

        # 提取数字
        numbers = re.findall(r'\d+\.?\d*[万千百亿]?', reference)
        key_entities.extend(numbers)

        # 提取长词组（2-4字中文词）
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', reference)
        # 过滤常见词
        stopwords = {'的', '是', '在', '了', '和', '与', '及', '或', '等', '于', '从', '以'}
        words = [w for w in words if w not in stopwords and len(w) >= 3]
        key_entities.extend(words[:10])  # 限制数量

        if not key_entities:
            return 1.0, {"reason": "参考文本中无明显关键实体"}

        # 检查每个关键实体是否在上下文中
        matched_entities = [e for e in key_entities if e in combined_context]
        recall = len(matched_entities) / len(key_entities) if key_entities else 0.0

        details = {
            "total_entities": len(key_entities),
            "matched_entities": len(matched_entities),
            "missing_entities": [e for e in key_entities if e not in combined_context]
        }

        return round(recall, 3), details

    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> EvaluationResult:
        """
        综合评估 RAG 系统性能

        Args:
            query: 用户问题
            answer: LLM 生成的答案
            contexts: 检索到的上下文列表
            ground_truth: 标准答案（可选）

        Returns:
            EvaluationResult: 评估结果
        """
        logger.info(f"开始评估: query='{query[:30]}...'")

        # 评估各维度
        faithfulness, f_details = self.evaluate_faithfulness(answer, contexts)
        answer_relevancy, ar_details = self.evaluate_answer_relevancy(query, answer)
        context_precision, cp_details = self.evaluate_context_precision(query, contexts)
        context_recall, cr_details = self.evaluate_context_recall(answer, contexts, ground_truth)

        # 汇总详细信息
        details = {
            "faithfulness": f_details,
            "answer_relevancy": ar_details,
            "context_precision": cp_details,
            "context_recall": cr_details
        }

        result = EvaluationResult(
            query=query,
            answer=answer,
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_precision=context_precision,
            context_recall=context_recall,
            details=details
        )

        logger.info(f"评估完成: {result.summary()}")
        return result


def batch_evaluate(
    test_cases: List[dict],
    evaluator: Optional[RAGEvaluator] = None
) -> dict:
    """
    批量评估多个测试用例

    Args:
        test_cases: 测试用例列表，每项包含 query, answer, contexts, ground_truth
        evaluator: 评估器实例

    Returns:
        批量评估报告
    """
    if evaluator is None:
        evaluator = RAGEvaluator()

    results = []
    for case in test_cases:
        result = evaluator.evaluate(
            query=case["query"],
            answer=case["answer"],
            contexts=case.get("contexts", []),
            ground_truth=case.get("ground_truth")
        )
        results.append(result.to_dict())

    # 计算汇总统计
    total = len(results)
    avg_faithfulness = sum(r["faithfulness"] for r in results) / total if total else 0
    avg_answer_relevancy = sum(r["answer_relevancy"] for r in results) / total if total else 0
    avg_context_precision = sum(r["context_precision"] for r in results) / total if total else 0
    avg_context_recall = sum(r["context_recall"] for r in results) / total if total else 0
    avg_overall = sum(r["overall_score"] for r in results) / total if total else 0

    # 通过率
    passed = sum(1 for r in results if r["overall_score"] >= 0.6)

    summary = {
        "total_cases": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 2) if total else 0,
        "avg_scores": {
            "faithfulness": round(avg_faithfulness, 3),
            "answer_relevancy": round(avg_answer_relevancy, 3),
            "context_precision": round(avg_context_precision, 3),
            "context_recall": round(avg_context_recall, 3),
            "overall": round(avg_overall, 3)
        },
        "results": results
    }

    return summary
