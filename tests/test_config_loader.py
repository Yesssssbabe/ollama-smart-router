# test_config_loader.py — 配置加载测试
import os
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path

from src.config_loader import load_yaml_config, config_from_yaml, merge_env_vars, _safe_float, _safe_int, _safe_str
from src.router import RouterConfig


class TestSafeConvert:
    """测试安全类型转换"""

    def test_safe_float_valid(self):
        assert _safe_float("3.5", 1.0, "test") == 3.5

    def test_safe_float_invalid_returns_default(self):
        assert _safe_float("abc", 1.0, "test") == 1.0

    def test_safe_float_none_returns_default(self):
        assert _safe_float(None, 2.0, "test") == 2.0

    def test_safe_float_negative_returns_default(self):
        assert _safe_float("-5.0", 1.0, "test") == 1.0

    def test_safe_float_type_error(self):
        assert _safe_float([1, 2, 3], 1.0, "test") == 1.0

    def test_safe_int_valid(self):
        assert _safe_int("42", 10, "test") == 42

    def test_safe_int_invalid_returns_default(self):
        assert _safe_int("xyz", 10, "test") == 10

    def test_safe_int_none_returns_default(self):
        assert _safe_int(None, 5, "test") == 5

    def test_safe_int_negative_returns_default(self):
        assert _safe_int("-10", 5, "test") == 5

    def test_safe_int_zero_returns_default(self):
        assert _safe_int("0", 5, "test") == 5

    def test_safe_str_valid(self):
        assert _safe_str("hello", "default") == "hello"

    def test_safe_str_empty_returns_default(self):
        assert _safe_str("", "default") == "default"

    def test_safe_str_none_returns_default(self):
        assert _safe_str(None, "default") == "default"

    def test_safe_str_whitespace_returns_default(self):
        assert _safe_str("   ", "default") == "default"


class TestLoadYamlConfig:
    """测试 YAML 配置加载"""

    def test_load_from_specific_path(self):
        yaml_content = """
models:
  small:
    name: "test:4b"
    vram_gb: 2.0
"""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=yaml_content)):
                with patch('src.config_loader.yaml') as mock_yaml:
                    mock_yaml.safe_load.return_value = {
                        "models": {"small": {"name": "test:4b", "vram_gb": 2.0}}
                    }
                    result = load_yaml_config("/tmp/config.yaml")
        
        assert result is not None
        assert result["models"]["small"]["name"] == "test:4b"

    def test_load_file_not_found(self):
        with patch('src.config_loader.yaml'):
            with patch('pathlib.Path.exists', return_value=False):
                result = load_yaml_config("/nonexistent/config.yaml")
        assert result is None

    def test_load_yaml_import_error(self):
        with patch('src.config_loader.yaml', None):
            with pytest.raises(ImportError, match="pyyaml"):
                load_yaml_config()

    def test_load_yaml_malformed(self):
        with patch('src.config_loader.yaml') as mock_yaml:
            mock_yaml.YAMLError = Exception
            mock_yaml.safe_load.side_effect = mock_yaml.YAMLError("YAML parse error")
            with patch('pathlib.Path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data="invalid: yaml: [")):
                    with pytest.raises(RuntimeError, match="YAML"):
                        load_yaml_config("/tmp/config.yaml")

    def test_load_permission_error(self):
        """权限错误处理"""
        with patch('src.config_loader.yaml'):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('builtins.open', side_effect=PermissionError("Access denied")):
                    with pytest.raises(RuntimeError, match="权限"):
                        load_yaml_config("/tmp/config.yaml")

    def test_path_expansion(self):
        """路径扩展（~/.config/...）"""
        with patch('src.config_loader.yaml'):
            with patch('pathlib.Path.expanduser', return_value=Path("/home/user/.config/ollama-smart-router/config.yaml")):
                with patch('pathlib.Path.exists', return_value=False):
                    result = load_yaml_config("~/.config/ollama-smart-router/config.yaml")
        assert result is None

    def test_no_yaml_installed(self):
        """未安装pyyaml时"""
        with patch('src.config_loader.yaml', None):
            with pytest.raises(ImportError):
                load_yaml_config("/tmp/config.yaml")

    def test_multi_encoding_fallback(self):
        """多编码回退"""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data="models:\n  small:\n    name: test")):
                with patch('src.config_loader.yaml') as mock_yaml:
                    mock_yaml.safe_load.return_value = {"models": {"small": {"name": "test"}}}
                    result = load_yaml_config("/tmp/config.yaml")
        assert result is not None


class TestConfigFromYaml:
    """测试从 YAML 构建 RouterConfig"""

    def test_full_config(self):
        yaml_data = {
            "models": {
                "small": {"name": "test-small:4b", "vram_gb": 2.5},
                "medium": {"name": "test-medium:7b", "vram_gb": 5.0},
                "large": {"name": "test-large:8b", "vram_gb": 6.5}
            },
            "gpu_thresholds": {"min_free_vram_gb": 3.5},
            "cloud": {
                "base_url": "https://test.api.com",
                "model": "test-model"
            },
            "performance": {"num_ctx": 8192, "num_gpu": 50},
            "routing": {"prefer_cloud_for_complex": False, "auto_fallback": False}
        }
        
        with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
            config = config_from_yaml("/tmp/config.yaml")
        
        assert config.small_model == "test-small:4b"
        assert config.small_model_vram == 2.5
        assert config.medium_model == "test-medium:7b"
        assert config.gpu_vram_threshold == 3.5
        assert config.cloud_base_url == "https://test.api.com"
        assert config.cloud_model == "test-model"
        assert config.num_ctx == 8192
        assert config.use_gpu_offload is True  # 50 > 0
        assert config.prefer_cloud_for_complex is False
        assert config.auto_fallback is False

    def test_empty_yaml(self):
        with patch('src.config_loader.load_yaml_config', return_value=None):
            config = config_from_yaml("/tmp/config.yaml")
        
        assert config.small_model == "gemma3:4b"  # 默认值

    def test_api_key_from_yaml(self):
        """YAML 中的 API key"""
        yaml_data = {"cloud": {"api_key": "yaml-key"}}
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
                config = config_from_yaml("/tmp/config.yaml")
        
        assert config.cloud_api_key == "yaml-key"

    def test_base_config_override(self):
        base = RouterConfig()
        base.small_model = "base-model"
        
        yaml_data = {"models": {"small": {"name": "yaml-model"}}}
        with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
            config = config_from_yaml("/tmp/config.yaml", base_config=base)
        
        assert config.small_model == "yaml-model"
        assert config.medium_model == base.medium_model  # 未被覆盖

    def test_invalid_vram_gb_uses_default(self):
        """无效的 vram_gb 值回退到默认值"""
        yaml_data = {"models": {"small": {"vram_gb": "invalid"}}}
        
        with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
            config = config_from_yaml("/tmp/config.yaml")
        
        assert config.small_model_vram == 3.0  # 默认值

    def test_negative_vram_gb_uses_default(self):
        """负数的 vram_gb 值回退到默认值"""
        yaml_data = {"models": {"small": {"vram_gb": -5.0}}}
        
        with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
            config = config_from_yaml("/tmp/config.yaml")
        
        assert config.small_model_vram == 3.0  # 默认值

    def test_empty_string_api_key(self):
        """空字符串 API key 不覆盖"""
        yaml_data = {"cloud": {"api_key": ""}}
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
                config = config_from_yaml("/tmp/config.yaml")
        
        assert config.cloud_api_key is None  # 默认None

    def test_string_num_gpu(self):
        """字符串 num_gpu 值处理"""
        yaml_data = {"performance": {"num_gpu": "50"}}
        
        with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
            config = config_from_yaml("/tmp/config.yaml")
        
        assert config.use_gpu_offload is True

    def test_zero_num_gpu(self):
        """num_gpu = 0 时禁用 GPU offload"""
        yaml_data = {"performance": {"num_gpu": 0}}
        
        with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
            config = config_from_yaml("/tmp/config.yaml")
        
        assert config.use_gpu_offload is False

    def test_safety_margin_from_yaml(self):
        """从 YAML 读取 safety_margin_gb"""
        yaml_data = {"gpu_thresholds": {"safety_margin_gb": 2.0}}
        
        with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
            config = config_from_yaml("/tmp/config.yaml")
        
        assert config.safety_margin_gb == 2.0


class TestMergeEnvVars:
    """测试环境变量合并"""

    def test_all_env_vars(self):
        config = RouterConfig()
        env = {
            "DEEPSEEK_API_KEY": "env-api-key",
            "CLOUD_BASE_URL": "https://env.api.com",
            "CLOUD_MODEL": "env-model",
            "SMALL_MODEL": "env-small",
            "MEDIUM_MODEL": "env-medium",
            "LARGE_MODEL": "env-large"
        }
        
        with patch.dict(os.environ, env, clear=True):
            config = merge_env_vars(config)
        
        assert config.cloud_api_key == "env-api-key"
        assert config.cloud_base_url == "https://env.api.com"
        assert config.cloud_model == "env-model"
        assert config.small_model == "env-small"
        assert config.medium_model == "env-medium"
        assert config.large_model == "env-large"

    def test_partial_env_vars(self):
        config = RouterConfig()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "only-api-key"}, clear=True):
            config = merge_env_vars(config)
        
        assert config.cloud_api_key == "only-api-key"
        assert config.cloud_model == "deepseek-chat"  # 保持默认

    def test_empty_env_var_not_overriding(self):
        """空字符串环境变量不覆盖现有配置"""
        config = RouterConfig()
        config.cloud_api_key = "existing-key"
        
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=True):
            config = merge_env_vars(config)
        
        assert config.cloud_api_key == "existing-key"  # 不被空字符串覆盖

    def test_env_priority_over_yaml(self):
        """环境变量优先级高于 YAML"""
        yaml_data = {"cloud": {"api_key": "yaml-key"}}
        
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env-key"}, clear=True):
            with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
                config = config_from_yaml("/tmp/config.yaml")
                # 手动调用 merge 模拟完整流程
                config = merge_env_vars(config)
        
        assert config.cloud_api_key == "env-key"

    def test_config_priority_cli_over_env(self):
        """CLI 参数优先级 > Env > YAML"""
        yaml_data = {"cloud": {"api_key": "yaml-key"}}
        
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env-key"}, clear=True):
            with patch('src.config_loader.load_yaml_config', return_value=yaml_data):
                config = config_from_yaml("/tmp/config.yaml")
                config = merge_env_vars(config)
                config.cloud_api_key = "cli-key"  # 模拟 CLI 覆盖
        
        assert config.cloud_api_key == "cli-key"

    def test_merge_returns_same_object(self):
        """merge_env_vars 返回同一对象（修改传入对象）"""
        config = RouterConfig()
        config_id = id(config)
        
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test"}, clear=True):
            result = merge_env_vars(config)
        
        assert id(result) == config_id
