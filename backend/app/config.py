import os
from contextvars import ContextVar, Token
from typing import Dict, List


class AppConfig:
    _runtime_overrides_by_client: Dict[str, Dict[str, str]] = {}
    _request_runtime_overrides: ContextVar[Dict[str, str] | None] = ContextVar("sqlguard_request_runtime_overrides", default=None)
    _request_client_id: ContextVar[str] = ContextVar("sqlguard_request_client_id", default="default")

    @staticmethod
    def _normalize_client_id(client_id: str | None) -> str:
        value = (client_id or "").strip()
        if not value:
            return "default"
        return value[:120]

    @staticmethod
    def bind_request_client(client_id: str | None) -> tuple[Token, Token]:
        normalized = AppConfig._normalize_client_id(client_id)
        overrides = AppConfig._runtime_overrides_by_client.get(normalized, {})
        token_client = AppConfig._request_client_id.set(normalized)
        token_overrides = AppConfig._request_runtime_overrides.set(overrides)
        return token_client, token_overrides

    @staticmethod
    def reset_request_client(tokens: tuple[Token, Token]) -> None:
        token_client, token_overrides = tokens
        AppConfig._request_client_id.reset(token_client)
        AppConfig._request_runtime_overrides.reset(token_overrides)

    @staticmethod
    def current_client_id() -> str:
        return AppConfig._request_client_id.get()

    @staticmethod
    def _raw_env(name: str, default: str = "") -> str:
        runtime_overrides = AppConfig._request_runtime_overrides.get() or {}
        if name in runtime_overrides:
            return str(runtime_overrides.get(name, ""))
        return os.getenv(name, default)

    @staticmethod
    def _csv_env(name: str) -> List[str]:
        raw = AppConfig._raw_env(name, "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _map_env(name: str) -> Dict[str, str]:
        raw = AppConfig._raw_env(name, "").strip()
        if not raw:
            return {}
        mapping: Dict[str, str] = {}
        for part in raw.split(","):
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            key = key.strip()
            value = value.strip().upper()
            if not key or value not in {"P0", "P1", "P2", "P3"}:
                continue
            mapping[key] = value
        return mapping

    @staticmethod
    def _float_env(name: str, default: float, min_value: float, max_value: float) -> float:
        raw = AppConfig._raw_env(name, "").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            return default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _int_env(name: str, default: int, min_value: int, max_value: int) -> int:
        raw = AppConfig._raw_env(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _bool_env(name: str, default: bool) -> bool:
        raw = AppConfig._raw_env(name, "").strip().lower()
        if not raw:
            return default
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return default

    @staticmethod
    def ai_provider() -> str:
        return AppConfig._raw_env("SQLGUARD_AI_PROVIDER", "ollama").strip().lower()

    @staticmethod
    def ai_base_url() -> str:
        return AppConfig._raw_env("SQLGUARD_AI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")

    @staticmethod
    def ai_model() -> str:
        return AppConfig._raw_env("SQLGUARD_AI_MODEL", "gpt-4o-mini").strip()

    @staticmethod
    def ai_api_key() -> str:
        return AppConfig._raw_env("SQLGUARD_AI_API_KEY", "").strip()

    @staticmethod
    def api_auth_token() -> str:
        return AppConfig._raw_env("SQLGUARD_API_TOKEN", "").strip()

    @staticmethod
    def config_endpoint_enabled() -> bool:
        return AppConfig._bool_env("SQLGUARD_EXPOSE_CONFIG", False)

    @staticmethod
    def ollama_base_url() -> str:
        return AppConfig._raw_env("SQLGUARD_OLLAMA_BASE_URL", "http://cn212001352.bilibili.local:11434").strip().rstrip("/")

    @staticmethod
    def ollama_model() -> str:
        return AppConfig._raw_env("SQLGUARD_OLLAMA_MODEL", "qwen3.5:9b").strip()

    @staticmethod
    def _timeout_seconds_env(name: str, default_seconds: float, min_value: float, max_value: float) -> float:
        raw = AppConfig._raw_env(name, "").strip()
        if not raw:
            return default_seconds
        try:
            value = float(raw)
        except ValueError:
            return default_seconds

        # Accept both seconds and milliseconds in configuration input.
        if value > max_value:
            value = value / 1000.0
        return max(min_value, min(max_value, value))

    @staticmethod
    def ai_temperature() -> float:
        return AppConfig._float_env("SQLGUARD_AI_TEMPERATURE", 0.0, 0.0, 1.0)

    @staticmethod
    def ai_seed() -> int:
        return AppConfig._int_env("SQLGUARD_AI_SEED", 42, 0, 2_147_483_647)

    @staticmethod
    def ai_http_timeout_seconds() -> float:
        return AppConfig._timeout_seconds_env("SQLGUARD_AI_HTTP_TIMEOUT", 30.0, 5.0, 600.0)

    @staticmethod
    def ai_max_retries() -> int:
        return AppConfig._int_env("SQLGUARD_AI_MAX_RETRIES", 2, 1, 5)

    @staticmethod
    def ai_schema_fallback_enabled() -> bool:
        return AppConfig._bool_env("SQLGUARD_AI_SCHEMA_FALLBACK", True)

    @staticmethod
    def ai_dedupe_create_structures() -> bool:
        return AppConfig._bool_env("SQLGUARD_AI_DEDUPE_CREATE_STRUCTURES", True)

    @staticmethod
    def ai_max_sql_chars() -> int:
        return AppConfig._int_env("SQLGUARD_AI_MAX_SQL_CHARS", 20_000, 2_000, 500_000)

    @staticmethod
    def sql_parser_debug_enabled() -> bool:
        return AppConfig._bool_env("SQLGUARD_SQL_PARSER_DEBUG", False)

    @staticmethod
    def sqlglot_warning_enabled() -> bool:
        return AppConfig._bool_env("SQLGUARD_SQLGLOT_WARNING", False)

    @staticmethod
    def ollama_http_timeout_seconds() -> float:
        return AppConfig._timeout_seconds_env("SQLGUARD_OLLAMA_HTTP_TIMEOUT", 30.0, 5.0, 1200.0)

    @staticmethod
    def update_runtime_ai_config(payload: Dict[str, str], client_id: str | None = None) -> dict:
        allowed_keys = {
            "SQLGUARD_AI_PROVIDER",
            "SQLGUARD_AI_BASE_URL",
            "SQLGUARD_AI_MODEL",
            "SQLGUARD_AI_API_KEY",
            "SQLGUARD_AI_HTTP_TIMEOUT",
            "SQLGUARD_OLLAMA_BASE_URL",
            "SQLGUARD_OLLAMA_MODEL",
            "SQLGUARD_OLLAMA_HTTP_TIMEOUT",
        }

        normalized_client = AppConfig._normalize_client_id(client_id)
        scoped_overrides = dict(AppConfig._runtime_overrides_by_client.get(normalized_client, {}))

        for key, value in payload.items():
            if key not in allowed_keys:
                continue
            scoped_overrides[key] = str(value).strip()

        AppConfig._runtime_overrides_by_client[normalized_client] = scoped_overrides

        return AppConfig.runtime_ai_config_view(client_id=normalized_client, mask_secret=True)

    @staticmethod
    def runtime_ai_config_view(client_id: str | None = None, mask_secret: bool = True) -> dict:
        normalized_client = AppConfig._normalize_client_id(client_id) if client_id is not None else AppConfig.current_client_id()
        scoped_overrides = AppConfig._runtime_overrides_by_client.get(normalized_client, {})

        token_client = AppConfig._request_client_id.set(normalized_client)
        token_overrides = AppConfig._request_runtime_overrides.set(scoped_overrides)
        try:
            key_value = AppConfig.ai_api_key()
            return {
                "client_id": normalized_client,
                "provider": AppConfig.ai_provider(),
                "ai_base_url": AppConfig.ai_base_url(),
                "ai_model": AppConfig.ai_model(),
                "ai_api_key": ("***" if (mask_secret and key_value) else key_value),
                "ai_api_key_configured": bool(key_value),
                "ai_http_timeout": AppConfig._raw_env("SQLGUARD_AI_HTTP_TIMEOUT", "30000").strip() or "30000",
                "ollama_base_url": AppConfig.ollama_base_url(),
                "ollama_model": AppConfig.ollama_model(),
                "ollama_http_timeout": AppConfig._raw_env("SQLGUARD_OLLAMA_HTTP_TIMEOUT", "30000").strip() or "30000",
                "runtime_override_count": len(scoped_overrides),
            }
        finally:
            AppConfig._request_client_id.reset(token_client)
            AppConfig._request_runtime_overrides.reset(token_overrides)

    @staticmethod
    def rule_policy_view() -> dict:
        return {
            "enabled_rules": AppConfig._csv_env("SQLGUARD_ENABLED_RULES"),
            "disabled_rules": AppConfig._csv_env("SQLGUARD_DISABLED_RULES"),
            "enabled_categories": AppConfig._csv_env("SQLGUARD_ENABLED_RULE_CATEGORIES"),
            "severity_overrides": AppConfig._map_env("SQLGUARD_RULE_SEVERITY_OVERRIDES"),
        }

    @staticmethod
    def default_suppressions() -> List[dict]:
        rule_ids = AppConfig._csv_env("SQLGUARD_SUPPRESS_RULES")
        return [{"rule_id": rid, "scope": "global"} for rid in rule_ids]

    @staticmethod
    def config_view() -> dict:
        return {
            "provider": AppConfig.ai_provider(),
            "ai_model": AppConfig.ai_model(),
            "ai_key_configured": bool(AppConfig.ai_api_key()),
            "ollama_model": AppConfig.ollama_model(),
            "ai_temperature": AppConfig.ai_temperature(),
            "ai_seed": AppConfig.ai_seed(),
            "ai_http_timeout_seconds": AppConfig.ai_http_timeout_seconds(),
            "ai_max_retries": AppConfig.ai_max_retries(),
            "ai_schema_fallback_enabled": AppConfig.ai_schema_fallback_enabled(),
            "ai_dedupe_create_structures": AppConfig.ai_dedupe_create_structures(),
            "ai_max_sql_chars": AppConfig.ai_max_sql_chars(),
            "ollama_http_timeout_seconds": AppConfig.ollama_http_timeout_seconds(),
            "rule_policy": AppConfig.rule_policy_view(),
            "default_suppressions": AppConfig.default_suppressions(),
            "api_auth_enabled": bool(AppConfig.api_auth_token()),
            "config_endpoint_enabled": AppConfig.config_endpoint_enabled(),
        }
