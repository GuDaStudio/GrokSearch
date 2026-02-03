import os
import json
from pathlib import Path

class Config:
    _instance = None
    _SETUP_COMMAND = (
        'claude mcp add-json grok-search --scope user '
        '\'{"type":"stdio","command":"uvx","args":["--from",'
        '"git+https://github.com/GuDaStudio/GrokSearch","grok-search"],'
        '"env":{"GROK_API_URL":"your-api-url","GROK_API_KEY":"your-api-key"}}\''
    )
    _DEFAULT_MODEL = "grok-4-fast"

    # 字段名映射: 外部名 -> (config.json键, 环境变量名, 默认值, 类型)
    _FIELD_MAP = {
        "API_URL": ("api_url", "GROK_API_URL", None, str),
        "API_KEY": ("api_key", "GROK_API_KEY", None, str),
        "MODEL": ("model", None, "grok-4-fast", str),
        "DEBUG": ("debug", "GROK_DEBUG", False, bool),
        "LOG_LEVEL": ("log_level", "GROK_LOG_LEVEL", "INFO", str),
        "LOG_DIR": ("log_dir", "GROK_LOG_DIR", "logs", str),
        "PROVIDER": ("provider", "PROVIDER", "grok", str),
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_file = None
            cls._instance._cache = {}
        return cls._instance

    @property
    def config_file(self) -> Path:
        if self._config_file is None:
            config_dir = Path.home() / ".config" / "grok-search"
            config_dir.mkdir(parents=True, exist_ok=True)
            self._config_file = config_dir / "config.json"
        return self._config_file

    def _load_config_file(self) -> dict:
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_config_file(self, config_data: dict) -> None:
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            raise ValueError(f"无法保存配置文件: {str(e)}")

    def _get_value(self, field: str):
        """通用配置读取: config.json > 环境变量 > 默认值"""
        if field not in self._FIELD_MAP:
            raise ValueError(f"未知配置字段: {field}")

        json_key, env_var, default, val_type = self._FIELD_MAP[field]

        # 优先从缓存读取
        if json_key in self._cache:
            return self._cache[json_key]

        # 从 config.json 读取
        config_data = self._load_config_file()
        if json_key in config_data:
            value = config_data[json_key]
            self._cache[json_key] = value
            return value

        # 从环境变量读取
        if env_var:
            env_value = os.getenv(env_var)
            if env_value is not None:
                if val_type == bool:
                    return env_value.lower() in ("true", "1", "yes")
                return env_value

        return default

    def set_config(self, field: str, value) -> dict:
        """通用配置写入"""
        if field not in self._FIELD_MAP:
            raise ValueError(f"未知配置字段: {field}")

        json_key, _, _, val_type = self._FIELD_MAP[field]
        old_value = self._get_value(field)

        # 类型转换
        if val_type == bool and isinstance(value, str):
            value = value.lower() in ("true", "1", "yes")

        config_data = self._load_config_file()
        config_data[json_key] = value
        self._save_config_file(config_data)
        self._cache[json_key] = value

        return {"field": field, "old_value": old_value, "new_value": value}

    @property
    def retry_max_attempts(self) -> int:
        return int(os.getenv("GROK_RETRY_MAX_ATTEMPTS", "3"))

    @property
    def retry_multiplier(self) -> float:
        return float(os.getenv("GROK_RETRY_MULTIPLIER", "1"))

    @property
    def retry_max_wait(self) -> int:
        return int(os.getenv("GROK_RETRY_MAX_WAIT", "10"))

    @property
    def debug_enabled(self) -> bool:
        return self._get_value("DEBUG")

    @property
    def api_url(self) -> str:
        url = self._get_value("API_URL")
        if not url:
            raise ValueError(
                f"API URL 未配置！\n"
                f"请使用以下命令配置 MCP 服务器：\n{self._SETUP_COMMAND}"
            )
        return url

    @property
    def api_key(self) -> str:
        key = self._get_value("API_KEY")
        if not key:
            raise ValueError(
                f"API Key 未配置！\n"
                f"请使用以下命令配置 MCP 服务器：\n{self._SETUP_COMMAND}"
            )
        return key

    @property
    def provider(self) -> str:
        return self._get_value("PROVIDER").lower()

    @property
    def log_level(self) -> str:
        level = self._get_value("LOG_LEVEL")
        return level.upper() if level else "INFO"

    @property
    def log_dir(self) -> Path:
        log_dir_str = self._get_value("LOG_DIR") or "logs"
        if Path(log_dir_str).is_absolute():
            return Path(log_dir_str)
        user_log_dir = Path.home() / ".config" / "grok-search" / log_dir_str
        user_log_dir.mkdir(parents=True, exist_ok=True)
        return user_log_dir

    @property
    def model(self) -> str:
        return self._get_value("MODEL")

    @staticmethod
    def _mask_api_key(key: str) -> str:
        """脱敏显示 API Key，只显示前后各 4 个字符"""
        if not key or len(key) <= 8:
            return "***"
        return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"

    def get_config_info(self) -> dict:
        """获取配置信息（API Key 已脱敏）"""
        try:
            api_url = self.api_url
            api_key_masked = self._mask_api_key(self.api_key)
            config_status = "✅ 配置完整"
        except ValueError as e:
            api_url = "未配置"
            api_key_masked = "未配置"
            config_status = f"❌ 配置错误: {str(e)}"

        return {
            "PROVIDER": self.provider,
            "API_URL": api_url,
            "API_KEY": api_key_masked,
            "MODEL": self.model,
            "DEBUG": self.debug_enabled,
            "LOG_LEVEL": self.log_level,
            "LOG_DIR": str(self.log_dir),
            "config_status": config_status
        }

config = Config()
