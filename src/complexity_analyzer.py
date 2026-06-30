"""
任务复杂度分析模块
使用启发式规则和轻量级模型自动评估任务复杂度
"""

import functools
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple


class TaskComplexity(Enum):
    """任务复杂度等级"""
    SIMPLE = "simple"      # 简单任务：本地小模型GPU
    MEDIUM = "medium"      # 中等任务：本地大模型CPU
    COMPLEX = "complex"    # 复杂任务：云端API


@dataclass
class TaskAnalysis:
    """任务分析结果"""
    complexity: TaskComplexity
    confidence: float      # 置信度 0-1
    estimated_tokens: int  # 预估token数
    requires_code: bool    # 是否需要代码
    requires_reasoning: bool  # 是否需要推理


class ComplexityAnalyzer:
    """任务复杂度分析器"""
    
    # 关键词映射表
    SIMPLE_KEYWORDS = [
        "你好", "hi", "hello", "再见", "谢谢", "请问",
        "翻译", "解释单词", "什么意思", "定义", "简介",
        "天气", "时间", "日期", "计算器"
    ]
    
    MEDIUM_KEYWORDS = [
        "代码", "程序", "python", "javascript", "函数",
        "分析", "总结", "比较", "对比", "优化", "重构",
        "算法", "数据结构", "排序", "查找", "正则",
        "sql", "查询", "api", "接口", "调试", "错误"
    ]
    
    COMPLEX_KEYWORDS = [
        "论文", "研究", "学术", "深度分析", "综合",
        "架构设计", "系统设计", "算法设计", "数学证明",
        "复杂推理", "多步骤", "长篇", "详细报告",
        "创意写作", "小说", "故事", "诗歌",
        "法律", "医疗", "金融", "投资建议"
    ]
    
    def __init__(self):
        # 合并关键词为复合正则，减少扫描次数并预编译
        self._simple_re = re.compile(
            "|".join(re.escape(kw) for kw in self.SIMPLE_KEYWORDS), re.I
        )
        self._medium_re = re.compile(
            "|".join(re.escape(kw) for kw in self.MEDIUM_KEYWORDS), re.I
        )
        self._complex_re = re.compile(
            "|".join(re.escape(kw) for kw in self.COMPLEX_KEYWORDS), re.I
        )

    @staticmethod
    @functools.lru_cache(maxsize=512)
    def _cached_analyze(
        simple_score: int,
        medium_score: int,
        complex_score: int,
        length: int,
        code_blocks: int,
        inline_code: int,
        reasoning_indicators: int,
        chinese_chars: int,
        english_words: int,
    ) -> Tuple[str, float, int, bool, bool]:
        """缓存分析结果的核心计算（纯函数，避免重复正则扫描）

        H-9: 缓存键不再包含原始 prompt，仅使用已提取的特征值，防止隐私泄露。
        """
        requires_code = code_blocks > 0 or medium_score > 0
        requires_reasoning = reasoning_indicators >= 2 or complex_score > 0
        estimated_tokens = int(chinese_chars * 1.5 + english_words * 1.3 + length * 0.1)

        if complex_score > 0 or length > 1000 or code_blocks >= 2:
            complexity = TaskComplexity.COMPLEX.value
            confidence = min(0.9, 0.5 + complex_score * 0.1)
        elif medium_score > 0 or length > 300 or code_blocks == 1 or reasoning_indicators >= 2:
            complexity = TaskComplexity.MEDIUM.value
            confidence = min(0.85, 0.5 + medium_score * 0.1)
        elif simple_score > 0 and length < 200:
            complexity = TaskComplexity.SIMPLE.value
            confidence = min(0.9, 0.6 + simple_score * 0.1)
        else:
            complexity = TaskComplexity.MEDIUM.value
            confidence = 0.5

        return complexity, confidence, estimated_tokens, requires_code, requires_reasoning

    def analyze(self, prompt: str) -> TaskAnalysis:
        """
        分析任务复杂度
        
        分析维度：
        1. 文本长度
        2. 关键词匹配
        3. 代码块数量
        4. 问题深度指示词
        """
        # 输入验证
        if prompt is None:
            raise ValueError("prompt 不能为 None")
        if not isinstance(prompt, str):
            raise TypeError(f"prompt 必须是字符串类型，实际为 {type(prompt).__name__}")
        
        prompt = prompt.strip()
        if len(prompt) == 0:
            return TaskAnalysis(
                complexity=TaskComplexity.SIMPLE,
                confidence=0.0,
                estimated_tokens=0,
                requires_code=False,
                requires_reasoning=False
            )
        
        # 长度截断保护，避免正则性能问题
        MAX_ANALYSIS_LENGTH = 50000
        if len(prompt) > MAX_ANALYSIS_LENGTH:
            prompt = prompt[:MAX_ANALYSIS_LENGTH]
        
        prompt_lower = prompt.lower()
        length = len(prompt)
        
        # 计算关键词得分（使用复合正则一次性扫描）
        simple_score = len(self._simple_re.findall(prompt))
        medium_score = len(self._medium_re.findall(prompt))
        complex_score = len(self._complex_re.findall(prompt))

        # 检测代码相关内容
        code_blocks = len(re.findall(r'```[\s\S]*?```', prompt))
        inline_code = len(re.findall(r'`[^`]+`', prompt))

        # 检测推理需求
        reasoning_indicators = len(re.findall(
            r'为什么|怎么|如何|解释|分析|推导|证明|推理|逻辑|步骤',
            prompt
        ))

        # 预估token数 (粗略估计: 1个中文字符≈1.5 tokens, 1个英文单词≈1.3 tokens)
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', prompt))
        english_words = len(re.findall(r'[a-zA-Z]+', prompt))

        # 使用缓存避免重复计算相同输入（H-9: 不将原始 prompt 作为缓存键）
        complexity_value, confidence, estimated_tokens, requires_code, requires_reasoning = self._cached_analyze(
            simple_score,
            medium_score,
            complex_score,
            length,
            code_blocks,
            inline_code,
            reasoning_indicators,
            chinese_chars,
            english_words,
        )

        return TaskAnalysis(
            complexity=TaskComplexity(complexity_value),
            confidence=confidence,
            estimated_tokens=estimated_tokens,
            requires_code=requires_code,
            requires_reasoning=requires_reasoning
        )
    
    def quick_estimate(self, prompt: str) -> str:
        """快速估算，返回字符串标识"""
        result = self.analyze(prompt)
        return result.complexity.value


class ContextAnalyzer:
    """上下文分析器 - 用于多轮对话场景"""
    
    def __init__(self, max_context_length: int = 4096):
        self.max_context = max_context_length
        self.history_complexity = []
        
    def add_interaction(self, prompt: str, analyzer: ComplexityAnalyzer):
        """记录交互历史"""
        result = analyzer.analyze(prompt)
        self.history_complexity.append(result.complexity)
        
        # 保持最近10条记录
        if len(self.history_complexity) > 10:
            self.history_complexity.pop(0)
    
    def get_session_complexity(self) -> TaskComplexity:
        """获取当前会话整体复杂度趋势"""
        if not self.history_complexity:
            return TaskComplexity.MEDIUM
            
        from collections import Counter
        counts = Counter(self.history_complexity)
        
        # 如果复杂任务超过30%，整体视为复杂
        if counts[TaskComplexity.COMPLEX] >= len(self.history_complexity) * 0.3:
            return TaskComplexity.COMPLEX
        # 如果简单任务超过60%，整体视为简单
        elif counts[TaskComplexity.SIMPLE] >= len(self.history_complexity) * 0.6:
            return TaskComplexity.SIMPLE
        else:
            return TaskComplexity.MEDIUM
