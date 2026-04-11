"""
任务复杂度分析模块
使用启发式规则和轻量级模型自动评估任务复杂度
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional


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
        self.simple_patterns = [re.compile(kw, re.I) for kw in self.SIMPLE_KEYWORDS]
        self.medium_patterns = [re.compile(kw, re.I) for kw in self.MEDIUM_KEYWORDS]
        self.complex_patterns = [re.compile(kw, re.I) for kw in self.COMPLEX_KEYWORDS]
        
    def analyze(self, prompt: str) -> TaskAnalysis:
        """
        分析任务复杂度
        
        分析维度：
        1. 文本长度
        2. 关键词匹配
        3. 代码块数量
        4. 问题深度指示词
        """
        prompt_lower = prompt.lower()
        length = len(prompt)
        
        # 计算关键词得分
        simple_score = sum(1 for p in self.simple_patterns if p.search(prompt))
        medium_score = sum(1 for p in self.medium_patterns if p.search(prompt))
        complex_score = sum(1 for p in self.complex_patterns if p.search(prompt))
        
        # 检测代码相关内容
        code_blocks = len(re.findall(r'```[\s\S]*?```', prompt))
        inline_code = len(re.findall(r'`[^`]+`', prompt))
        requires_code = code_blocks > 0 or medium_score > 0
        
        # 检测推理需求
        reasoning_indicators = len(re.findall(
            r'为什么|怎么|如何|解释|分析|推导|证明|推理|逻辑|步骤',
            prompt
        ))
        requires_reasoning = reasoning_indicators >= 2 or complex_score > 0
        
        # 预估token数 (粗略估计: 1个中文字符≈1.5 tokens, 1个英文单词≈1.3 tokens)
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', prompt))
        english_words = len(re.findall(r'[a-zA-Z]+', prompt))
        estimated_tokens = int(chinese_chars * 1.5 + english_words * 1.3 + length * 0.1)
        
        # 综合判断复杂度
        if complex_score > 0 or length > 1000 or code_blocks >= 2:
            complexity = TaskComplexity.COMPLEX
            confidence = min(0.9, 0.5 + complex_score * 0.1)
        elif medium_score > 0 or length > 300 or code_blocks == 1 or reasoning_indicators >= 2:
            complexity = TaskComplexity.MEDIUM
            confidence = min(0.85, 0.5 + medium_score * 0.1)
        elif simple_score > 0 and length < 200:
            complexity = TaskComplexity.SIMPLE
            confidence = min(0.9, 0.6 + simple_score * 0.1)
        else:
            # 默认中等复杂度
            complexity = TaskComplexity.MEDIUM
            confidence = 0.5
            
        return TaskAnalysis(
            complexity=complexity,
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
