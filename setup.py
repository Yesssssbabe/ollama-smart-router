"""
Ollama Smart Router - 智能模型调度器

修复内容:
- HIGH-13: 修复 entry_points 为 src.cli:main，确保 pip install 后命令可用
- Critical-2: 添加 README.md / requirements.txt 文件缺失保护
"""

import os
from setuptools import setup, find_packages

# 安全读取文件，带缺失保护
long_description = ""
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "Ollama Smart Router - 智能模型调度器"

requirements = []
try:
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]
except FileNotFoundError:
    requirements = [
        "ollama>=0.4.0",
        "psutil>=5.9.0",
        "pyyaml>=6.0",
        "openai>=1.0.0",
    ]

setup(
    name="ollama-smart-router",
    version="0.1.0",
    author=os.getenv("PACKAGE_AUTHOR", "Anonymous"),
    author_email=os.getenv("PACKAGE_AUTHOR_EMAIL", "anonymous@example.com"),
    description="智能模型调度器 - 根据硬件状态自动选择最佳推理路径",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=os.getenv("PACKAGE_URL", "https://github.com/ollama-smart-router/ollama-smart-router"),
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "cloud": ["openai>=1.0.0"],
        "dev": ["pytest>=7.0.0", "black>=23.0.0", "ruff>=0.1.0"],
    },
    # HIGH-13: 修复为 src.cli:main，因为 cli 在 src 包下
    entry_points={
        "console_scripts": [
            "osr=src.cli:main",
            "ollama-router=src.cli:main",
        ],
    },
)
