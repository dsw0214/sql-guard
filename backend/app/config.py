import os


class AppConfig:
    @staticmethod
    def _float_env(name: str, default: float, min_value: float, max_value: float) -> float:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            return default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _int_env(name: str, default: int, min_value: int, max_value: int) -> int:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return max(min_value, min(max_value, value))

    @staticmethod
    def ai_provider() -> str:
        return os.getenv("SQLGUARD_AI_PROVIDER", "openai").strip().lower()

    @staticmethod
    def ai_base_url() -> str:
        return os.getenv("SQLGUARD_AI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")

    @staticmethod
    def ai_model() -> str:
        return os.getenv("SQLGUARD_AI_MODEL", "gpt-4o-mini").strip()

    @staticmethod
    def ai_api_key() -> str:
        return os.getenv("SQLGUARD_AI_API_KEY", "").strip()

    @staticmethod
    def ollama_base_url() -> str:
        return os.getenv("SQLGUARD_OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")

    @staticmethod
    def ollama_model() -> str:
        return os.getenv("SQLGUARD_OLLAMA_MODEL", "qwen2.5-coder:7b").strip()

    @staticmethod
    def ai_temperature() -> float:
        return AppConfig._float_env("SQLGUARD_AI_TEMPERATURE", 0.0, 0.0, 1.0)

    @staticmethod
    def ai_seed() -> int:
        return AppConfig._int_env("SQLGUARD_AI_SEED", 42, 0, 2_147_483_647)

    @staticmethod
    def ai_http_timeout_seconds() -> float:
        return AppConfig._float_env("SQLGUARD_AI_HTTP_TIMEOUT", 30.0, 5.0, 600.0)

    @staticmethod
    def ollama_http_timeout_seconds() -> float:
        return AppConfig._float_env("SQLGUARD_OLLAMA_HTTP_TIMEOUT", 300.0, 5.0, 1200.0)

    @staticmethod
    def config_view() -> dict:
        return {
            "provider": AppConfig.ai_provider(),
            "ai_base_url": AppConfig.ai_base_url(),
            "ai_model": AppConfig.ai_model(),
            "ai_key_configured": bool(AppConfig.ai_api_key()),
            "ollama_base_url": AppConfig.ollama_base_url(),
            "ollama_model": AppConfig.ollama_model(),
            "ai_temperature": AppConfig.ai_temperature(),
            "ai_seed": AppConfig.ai_seed(),
            "ai_http_timeout_seconds": AppConfig.ai_http_timeout_seconds(),
            "ollama_http_timeout_seconds": AppConfig.ollama_http_timeout_seconds(),
        }
