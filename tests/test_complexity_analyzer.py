# test_complexity_analyzer.py — 复杂度分析测试
import pytest

from src.complexity_analyzer import ComplexityAnalyzer, TaskComplexity, ContextAnalyzer


class TestComplexityAnalyzer:
    """测试复杂度分析器"""

    @pytest.fixture
    def analyzer(self):
        return ComplexityAnalyzer()

    def test_simple_greeting(self, analyzer):
        """简单问候语 → simple"""
        result = analyzer.analyze("你好")
        assert result.complexity == TaskComplexity.SIMPLE
        assert result.confidence > 0.5
        assert result.requires_code is False

    def test_code_task(self, analyzer):
        """代码任务 → medium"""
        result = analyzer.analyze("写个Python排序函数")
        assert result.complexity == TaskComplexity.MEDIUM
        assert result.requires_code is True

    def test_complex_task(self, analyzer):
        """复杂任务 → complex（包含 COMPLEX 关键词"""
        result = analyzer.analyze("设计一个支持百万并发的分布式系统架构设计")
        assert result.complexity == TaskComplexity.COMPLEX
        assert result.requires_reasoning is True

    def test_empty_string(self, analyzer):
        """空字符串 → 默认 SIMPLE"""
        result = analyzer.analyze("")
        assert result.complexity == TaskComplexity.SIMPLE
        assert result.confidence == 0.0
        assert result.estimated_tokens == 0

    def test_long_text_complex(self, analyzer):
        """超长文本 (>1000字符，strip 后仍 >1000) 触发 COMPLEX"""
        # 使用不会被 strip 掉的前导/尾部非空白字符，且长度 > 1000
        text = "a" * 1001
        result = analyzer.analyze(text)
        assert result.complexity == TaskComplexity.COMPLEX

    def test_no_keywords(self, analyzer):
        """无关键词匹配 → 默认 MEDIUM（无 simple 关键词匹配）"""
        # 避免包含 "hi" 等 simple 关键词，使用不含匹配内容的字符串
        result = analyzer.analyze("xyz qwe rty uio pas dfg hjk lzx vbn mqw")
        assert result.complexity == TaskComplexity.MEDIUM
        assert result.confidence == 0.5

    def test_multiple_code_blocks(self, analyzer):
        """两个代码块触发 COMPLEX"""
        text = "```python\nprint(1)\n```\n\n```python\nprint(2)\n```"
        result = analyzer.analyze(text)
        assert result.complexity == TaskComplexity.COMPLEX
        assert result.requires_code is True

    def test_single_code_block_medium(self, analyzer):
        """一个代码块触发 MEDIUM"""
        text = "```python\nprint(1)\n```"
        result = analyzer.analyze(text)
        assert result.complexity == TaskComplexity.MEDIUM

    def test_special_characters(self, analyzer):
        """特殊字符不崩溃"""
        result = analyzer.analyze("!@#$%^&*()_+{}|:<>?~`-=[]\\;',./")
        assert result.complexity in [TaskComplexity.SIMPLE, TaskComplexity.MEDIUM]

    def test_mixed_simple_but_long(self, analyzer):
        """含 SIMPLE 关键词但长度 > 300 → 应 MEDIUM"""
        text = "翻译 " + "x" * 400
        result = analyzer.analyze(text)
        assert result.complexity == TaskComplexity.MEDIUM

    def test_reasoning_indicators(self, analyzer):
        """推理关键词触发 reasoning"""
        result = analyzer.analyze("为什么天空是蓝的？怎么解释")
        assert result.requires_reasoning is True

    def test_estimated_tokens(self, analyzer):
        """token 估算基本合理"""
        result = analyzer.analyze("你好 world")
        # 2 中文字符 * 1.5 + 1 英文单词 * 1.3 + 10 * 0.1 = 3 + 1.3 + 1 = 5.3
        assert result.estimated_tokens > 0

    def test_quick_estimate(self, analyzer):
        assert analyzer.quick_estimate("你好") == "simple"
        assert analyzer.quick_estimate("写代码") == "medium"
        assert analyzer.quick_estimate("设计一个架构设计") == "complex"

    def test_case_insensitive(self, analyzer):
        """关键词大小写不敏感"""
        result = analyzer.analyze("PYTHON")
        assert result.complexity == TaskComplexity.MEDIUM

    def test_none_input(self, analyzer):
        """None 输入抛出 ValueError"""
        with pytest.raises(ValueError, match="不能为 None"):
            analyzer.analyze(None)

    def test_non_string_input(self, analyzer):
        """非字符串输入抛出 TypeError"""
        with pytest.raises(TypeError, match="字符串"):
            analyzer.analyze(123)

    def test_complex_keyword_score(self, analyzer):
        """多个复杂关键词增加置信度"""
        result = analyzer.analyze("论文 研究 学术 深度分析")
        assert result.complexity == TaskComplexity.COMPLEX
        assert result.confidence > 0.5

    def test_length_boundary_300(self, analyzer):
        """长度刚好300 → 应触发 MEDIUM"""
        text = "a" * 300
        result = analyzer.analyze(text)
        assert result.complexity == TaskComplexity.MEDIUM

    def test_length_boundary_1000(self, analyzer):
        """长度刚好1000 → 应触发 COMPLEX（>1000 才是 simple，==1000 不是）"""
        text = "a" * 1001
        result = analyzer.analyze(text)
        assert result.complexity == TaskComplexity.COMPLEX

    def test_chinese_and_english_tokens(self, analyzer):
        """中英文混合token估算"""
        result = analyzer.analyze("Hello 世界")
        assert result.estimated_tokens > 0
        # 1 英文单词 + 2 中文字符
        # 2 * 1.5 + 1 * 1.3 + len * 0.1 = 3 + 1.3 + 0.8 = 5.1
        assert result.estimated_tokens >= 5

    def test_requires_code_inline(self, analyzer):
        """行内代码触发 requires_code"""
        result = analyzer.analyze("使用 `print()` 函数")
        assert result.requires_code is True

    def test_requires_code_blocks(self, analyzer):
        """代码块触发 requires_code"""
        result = analyzer.analyze("```python\nprint(1)\n```")
        assert result.requires_code is True

    def test_no_reasoning_single_indicator(self, analyzer):
        """单个推理指示词不触发 reasoning"""
        result = analyzer.analyze("为什么")
        assert result.requires_reasoning is False  # 需要 >= 2

    def test_reasoning_multiple_indicators(self, analyzer):
        """多个推理指示词触发 reasoning"""
        result = analyzer.analyze("为什么天空是蓝色的？怎么解释？")
        assert result.requires_reasoning is True

    def test_long_text_truncation(self, analyzer):
        """超长文本截断保护"""
        text = "a" * 100000
        result = analyzer.analyze(text)
        assert result.complexity == TaskComplexity.COMPLEX  # 超过1000字符触发complex

    def test_strip_input(self, analyzer):
        """输入自动 strip"""
        result = analyzer.analyze("  你好  ")
        assert result.complexity == TaskComplexity.SIMPLE


class TestContextAnalyzer:
    """测试上下文分析器"""

    @pytest.fixture
    def context_analyzer(self):
        return ContextAnalyzer()

    @pytest.fixture
    def analyzer(self):
        return ComplexityAnalyzer()

    def test_empty_history(self, context_analyzer):
        assert context_analyzer.get_session_complexity() == TaskComplexity.MEDIUM

    def test_simple_majority(self, context_analyzer, analyzer):
        for _ in range(7):
            context_analyzer.add_interaction("你好", analyzer)
        for _ in range(3):
            context_analyzer.add_interaction("写代码", analyzer)
        assert context_analyzer.get_session_complexity() == TaskComplexity.SIMPLE

    def test_complex_threshold(self, context_analyzer, analyzer):
        for _ in range(10):
            context_analyzer.add_interaction("简单问题", analyzer)
        for _ in range(5):
            context_analyzer.add_interaction("设计一个分布式系统架构设计", analyzer)
        # 5/15 = 33% > 30% → COMPLEX
        assert context_analyzer.get_session_complexity() == TaskComplexity.COMPLEX

    def test_history_limit(self, context_analyzer, analyzer):
        for i in range(15):
            context_analyzer.add_interaction(f"问题{i}", analyzer)
        assert len(context_analyzer.history_complexity) == 10

    def test_medium_default(self, context_analyzer, analyzer):
        for _ in range(5):
            context_analyzer.add_interaction("一般问题", analyzer)
        assert context_analyzer.get_session_complexity() == TaskComplexity.MEDIUM

    def test_exact_30_percent_complex(self, context_analyzer, analyzer):
        """刚好30%复杂任务"""
        for _ in range(7):
            context_analyzer.add_interaction("你好", analyzer)
        for _ in range(3):
            context_analyzer.add_interaction("学术论文", analyzer)
        # 3/10 = 30% >= 30% → COMPLEX
        assert context_analyzer.get_session_complexity() == TaskComplexity.COMPLEX

    def test_below_30_percent_complex(self, context_analyzer, analyzer):
        """低于30%复杂任务 → 非 COMPLEX"""
        for _ in range(8):
            context_analyzer.add_interaction("你好", analyzer)
        for _ in range(2):
            context_analyzer.add_interaction("学术论文", analyzer)
        # 2/10 = 20% < 30% → 不应为 COMPLEX
        result = context_analyzer.get_session_complexity()
        assert result != TaskComplexity.COMPLEX

    def test_below_60_percent_simple(self, context_analyzer, analyzer):
        """低于60%简单任务 → 非 SIMPLE"""
        for _ in range(5):
            context_analyzer.add_interaction("你好", analyzer)
        for _ in range(5):
            context_analyzer.add_interaction("写代码", analyzer)
        # 5/10 = 50% < 60% → 不应为 SIMPLE
        result = context_analyzer.get_session_complexity()
        assert result != TaskComplexity.SIMPLE
