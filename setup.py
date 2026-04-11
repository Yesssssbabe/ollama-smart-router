"""
Ollama Smart Router - 智能模型调度器
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="ollama-smart-router",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="智能模型调度器 - 根据硬件状态自动选择最佳推理路径",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ollama-smart-router",
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
    entry_points={
        "console_scripts": [
            "osr=src.cli:main",
            "ollama-router=src.cli:main",
        ],
    },
)
