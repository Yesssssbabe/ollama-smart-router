# 贡献指南

感谢您对 Ollama Smart Router 的兴趣！

## 如何贡献

### 报告问题

1. 检查是否已存在相关Issue
2. 提供详细的复现步骤
3. 包含您的硬件配置和环境信息

### 提交代码

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 代码规范

- 使用 Black 格式化代码
- 遵循 PEP 8 规范
- 添加适当的文档字符串
- 为新功能编写测试

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/yourusername/ollama-smart-router.git
cd ollama-smart-router

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -r requirements.txt
pip install black ruff pytest

# 运行测试
pytest tests/

# 格式化代码
black src/
ruff check src/
```

## 开发路线图

- [ ] 支持更多云端API提供商
- [ ] 添加模型量化选项
- [ ] 实现智能批处理
- [ ] 添加Web界面
- [ ] 支持多GPU配置
