# test_cli.py — 命令行测试
import dataclasses
import pytest
import argparse
import sys
from unittest.mock import patch, Mock, MagicMock

from src.cli import (
    create_parser, interactive_mode, load_config, main,
    check_ollama_connection, print_ollama_error, print_error, print_tip,
    validate_config_path
)
from src.router import SmartRouter, RouterConfig, RoutingStrategy


class TestCreateParser:
    """测试参数解析器"""

    def test_default_values(self):
        parser = create_parser()
        args = parser.parse_args([])
        assert args.strategy == "auto"
        assert args.config is None
        assert args.prompt is None

    def test_strategy_choices(self):
        parser = create_parser()
        args = parser.parse_args(["-s", "gpu", "test prompt"])
        assert args.strategy == "gpu"
        assert args.prompt == "test prompt"

    def test_complexity_option(self):
        parser = create_parser()
        args = parser.parse_args(["-c", "simple", "test"])
        assert args.complexity == "simple"

    def test_interactive_flag(self):
        parser = create_parser()
        args = parser.parse_args(["-i"])
        assert args.interactive is True

    def test_list_models_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--list-models"])
        assert args.list_models is True

    def test_status_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--status"])
        assert args.status is True

    def test_config_path(self):
        parser = create_parser()
        args = parser.parse_args(["--config", "config.yaml"])
        assert args.config == "config.yaml"

    def test_invalid_strategy(self):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["-s", "invalid"])

    def test_model_override(self):
        parser = create_parser()
        args = parser.parse_args(["-m", "custom-model"])
        assert args.model == "custom-model"

    def test_help_displays(self, capsys):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["-h"])
        captured = capsys.readouterr()
        assert "Ollama Smart Router" in captured.out


class TestValidateConfigPath:
    """测试配置文件路径验证"""

    def test_valid_path(self):
        assert validate_config_path("config.yaml") == "config.yaml"

    def test_path_traversal(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validate_config_path("/etc/passwd")

    def test_path_traversal_absolute(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validate_config_path("/tmp/attack.yaml")

    def test_path_outside_home_and_cwd(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validate_config_path("/usr/share/config.yaml")

    def test_valid_home_path(self):
        assert validate_config_path("~/.config/ollama-smart-router/config.yaml") == "~/.config/ollama-smart-router/config.yaml"

    def test_valid_cwd_path(self):
        assert validate_config_path("config.yaml") == "config.yaml"

    def test_path_relative_inside_cwd(self):
        assert validate_config_path("./config.yaml") == "./config.yaml"

    def test_path_relative_parent(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validate_config_path("/usr/share/config.yaml")


class TestCheckOllamaConnection:
    """测试 Ollama 连接检查"""

    def test_connection_success(self):
        with patch('ollama.list', return_value={"models": []}):
            assert check_ollama_connection() is True

    def test_connection_failure(self):
        with patch('ollama.list', side_effect=Exception("Connection refused")):
            assert check_ollama_connection() is False

    def test_connection_timeout(self):
        with patch('ollama.list', side_effect=TimeoutError("timeout")):
            assert check_ollama_connection() is False

    def test_connection_called_each_time(self):
        """每次调用都会请求 ollama（无缓存）"""
        with patch('ollama.list', return_value={"models": []}) as mock_list:
            assert check_ollama_connection() is True
            assert check_ollama_connection() is True
        # 无缓存，每次调用都会请求
        assert mock_list.call_count == 2


class TestLoadConfig:
    """测试配置加载"""

    def test_load_from_args_no_config(self):
        parser = create_parser()
        args = parser.parse_args([])
        
        with patch('src.cli.config_from_yaml', return_value=RouterConfig()) as mock_yaml:
            with patch('src.cli.merge_env_vars', side_effect=lambda c: c) as mock_env:
                config = load_config(args)
        
        assert config is not None
        mock_yaml.assert_called_once_with(None)

    def test_load_from_args_with_valid_config(self):
        parser = create_parser()
        args = parser.parse_args(["--config", "config.yaml"])
        
        with patch('os.path.exists', return_value=True):
            with patch('src.cli.config_from_yaml', return_value=RouterConfig()) as mock_yaml:
                with patch('src.cli.merge_env_vars', side_effect=lambda c: c):
                    config = load_config(args)
        
        assert config is not None
        mock_yaml.assert_called_once_with("config.yaml")

    def test_model_override(self):
        parser = create_parser()
        args = parser.parse_args(["-m", "custom-model"])
        
        with patch('src.cli.config_from_yaml', return_value=RouterConfig()):
            with patch('src.cli.merge_env_vars', side_effect=lambda c: c):
                config = load_config(args)
        
        assert config.small_model == "custom-model"
        assert config.medium_model == "custom-model"
        assert config.large_model == "custom-model"

    def test_config_file_not_found_exits(self):
        """指定配置文件不存在时退出"""
        parser = create_parser()
        args = parser.parse_args(["--config", "nonexistent_config.yaml"])
        
        with pytest.raises(SystemExit, match="1"):
            load_config(args)

    def test_empty_model_not_override(self):
        """空字符串 model 不覆盖"""
        parser = create_parser()
        args = parser.parse_args(["-m", ""])
        
        base = RouterConfig(small_model="existing")
        with patch('src.cli.config_from_yaml', return_value=base):
            with patch('src.cli.merge_env_vars', side_effect=lambda c: c):
                config = load_config(args)
        
        assert config.small_model == "existing"

    def test_cloud_key_removed(self):
        """--cloud-key 已移除"""
        parser = create_parser()
        # --cloud-key 不存在，应被当作未知参数
        with pytest.raises(SystemExit):
            parser.parse_args(["--cloud-key", "secret"])


class TestMain:
    """测试主入口"""

    def test_status_mode(self, capsys):
        with patch('src.cli.GPUMonitor') as mock_gpu:
            mock_gpu.return_value.print_status = Mock()
            with patch('src.cli.CPUMonitor') as mock_cpu:
                mock_cpu.return_value.print_status = Mock()
                with patch('sys.argv', ['cli', '--status']):
                    result = main()
        
        assert result == 0

    def test_list_models(self, capsys):
        with patch('src.cli.load_config', return_value=RouterConfig()):
            with patch('src.cli.SmartRouter') as mock_router:
                mock_router.return_value.list_available_models.return_value = [
                    "gemma3:4b", "qwen2.5:7b"
                ]
                with patch('sys.argv', ['cli', '--list-models']):
                    result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "gemma3:4b" in captured.out

    def test_single_prompt(self, capsys):
        mock_result = Mock()
        mock_result.content = "Test response"
        
        with patch('src.cli.load_config', return_value=RouterConfig()):
            with patch('src.cli.SmartRouter') as mock_router:
                mock_router.return_value.route.return_value = mock_result
                with patch('src.cli.check_ollama_connection', return_value=True):
                    with patch('sys.argv', ['cli', 'Hello']):
                        result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "Test response" in captured.out

    def test_interactive_mode(self):
        with patch('src.cli.load_config', return_value=RouterConfig()):
            with patch('src.cli.SmartRouter'):
                with patch('src.cli.check_ollama_connection', return_value=True):
                    with patch('builtins.input', side_effect=["/quit"]):
                        with patch('sys.argv', ['cli', '-i']):
                            result = main()
        
        assert result == 0

    def test_ollama_not_connected(self, capsys):
        with patch('src.cli.load_config', return_value=RouterConfig()):
            with patch('src.cli.SmartRouter'):
                with patch('src.cli.check_ollama_connection', return_value=False):
                    with patch('sys.argv', ['cli', 'Hello']):
                        result = main()
        
        assert result == 1
        captured = capsys.readouterr()
        assert "无法连接" in captured.out

    def test_model_not_found_error(self, capsys):
        with patch('src.cli.load_config', return_value=RouterConfig()):
            with patch('src.cli.SmartRouter') as mock_router:
                mock_router.return_value.route.side_effect = RuntimeError(
                    "model not found"
                )
                with patch('src.cli.check_ollama_connection', return_value=True):
                    with patch('sys.argv', ['cli', 'Hello']):
                        result = main()
        
        assert result == 1
        captured = capsys.readouterr()
        assert "运行失败" in captured.out

    def test_connection_error(self, capsys):
        with patch('src.cli.load_config', return_value=RouterConfig()):
            with patch('src.cli.SmartRouter') as mock_router:
                mock_router.return_value.route.side_effect = Exception(
                    "connection refused"
                )
                with patch('src.cli.check_ollama_connection', return_value=True):
                    with patch('sys.argv', ['cli', 'Hello']):
                        result = main()
        
        assert result == 1
        captured = capsys.readouterr()
        assert "运行失败" in captured.out

    def test_cloud_strategy_no_ollama_check(self, capsys):
        """云端策略不需要检查 Ollama 连接"""
        mock_result = Mock()
        mock_result.content = "Cloud response"
        
        with patch('src.cli.load_config', return_value=RouterConfig()):
            with patch('src.cli.SmartRouter') as mock_router:
                mock_router.return_value.route.return_value = mock_result
                with patch('src.cli.check_ollama_connection', return_value=False):
                    with patch('sys.argv', ['cli', '--strategy', 'cloud', 'Hello']):
                        result = main()
        
        assert result == 0
        assert "Cloud response" in capsys.readouterr().out

    def test_interactive_mode_eof(self):
        """EOF 退出交互模式"""
        with patch('src.cli.load_config', return_value=RouterConfig()):
            with patch('src.cli.SmartRouter'):
                with patch('src.cli.check_ollama_connection', return_value=True):
                    with patch('builtins.input', side_effect=EOFError()):
                        with patch('sys.argv', ['cli', '-i']):
                            result = main()
        
        assert result == 0


class TestInteractiveMode:
    """测试交互模式"""

    def test_quit_command(self, capsys):
        router = Mock()
        with patch('builtins.input', side_effect=["/quit"]):
            interactive_mode(router)
        captured = capsys.readouterr()
        assert "再见" in captured.out

    def test_status_command(self, capsys):
        router = Mock()
        with patch('builtins.input', side_effect=["/status", "/quit"]):
            interactive_mode(router)
        router.gpu_monitor.print_status.assert_called_once()

    def test_stats_command(self, capsys):
        router = Mock()
        with patch('builtins.input', side_effect=["/stats", "/quit"]):
            interactive_mode(router)
        router.print_stats.assert_called_once()

    def test_help_command(self, capsys):
        router = Mock()
        with patch('builtins.input', side_effect=["/help", "/quit"]):
            interactive_mode(router)
        captured = capsys.readouterr()
        assert "/quit" in captured.out

    def test_setkey_command(self, capsys):
        router = SmartRouter(RouterConfig())
        with patch('builtins.input', side_effect=["/setkey", "/quit"]):
            with patch('getpass.getpass', return_value="secret-key"):
                interactive_mode(router)
        assert router.config.cloud_api_key == "secret-key"

    def test_unknown_command(self, capsys):
        router = Mock()
        with patch('builtins.input', side_effect=["/unknown", "/quit"]):
            interactive_mode(router)
        captured = capsys.readouterr()
        assert "未知命令" in captured.out

    def test_empty_input(self):
        router = Mock()
        with patch('builtins.input', side_effect=["", "/quit"]):
            interactive_mode(router)
        router.route.assert_not_called()  # 空输入不触发路由

    def test_keyboard_interrupt(self, capsys):
        router = Mock()
        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            interactive_mode(router)
        captured = capsys.readouterr()
        assert "再见" in captured.out

    def test_system_exit_propagation(self):
        """SystemExit 应传播而非被捕获"""
        router = Mock()
        with patch('builtins.input', side_effect=SystemExit()):
            with pytest.raises(SystemExit):
                interactive_mode(router)

    def test_normal_prompt(self, capsys):
        router = Mock()
        mock_result = Mock()
        mock_result.source = "local_gpu"
        mock_result.content = "Response text"
        router.route.return_value = mock_result
        
        with patch('builtins.input', side_effect=["Hello", "/quit"]):
            interactive_mode(router)
        
        router.route.assert_called_once_with("Hello")
        captured = capsys.readouterr()
        assert "Response text" in captured.out

    def test_error_handling(self, capsys):
        router = Mock()
        router.route.side_effect = Exception("Something went wrong")
        
        with patch('builtins.input', side_effect=["Hello", "/quit"]):
            interactive_mode(router)
        
        captured = capsys.readouterr()
        assert "错误" in captured.out

    def test_multiple_prompts(self, capsys):
        """多轮交互"""
        router = Mock()
        mock_result = Mock()
        mock_result.source = "local_gpu"
        mock_result.content = "Answer"
        router.route.return_value = mock_result
        
        with patch('builtins.input', side_effect=["Q1", "Q2", "/quit"]):
            interactive_mode(router)
        
        assert router.route.call_count == 2

    def test_long_input_rejected(self, capsys):
        """超长输入被拒绝"""
        router = Mock()
        long_input = "x" * 200001
        
        with patch('builtins.input', side_effect=[long_input, "/quit"]):
            interactive_mode(router)
        
        router.route.assert_not_called()
        captured = capsys.readouterr()
        assert "过长" in captured.out


class TestPrintFunctions:
    """测试输出函数"""

    def test_print_error(self, capsys):
        print_error("Something failed")
        captured = capsys.readouterr()
        assert "Something failed" in captured.out
        assert "❌" in captured.out

    def test_print_tip(self, capsys):
        print_tip("Try this")
        captured = capsys.readouterr()
        assert "Try this" in captured.out
        assert "💡" in captured.out

    def test_print_ollama_error(self, capsys):
        print_ollama_error()
        captured = capsys.readouterr()
        assert "Ollama" in captured.out
        assert "https://ollama.com" in captured.out

    def test_print_ollama_error_has_error_symbol(self, capsys):
        print_ollama_error()
        captured = capsys.readouterr()
        assert "❌" in captured.out
