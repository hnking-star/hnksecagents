"""核心配置模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RuntimeConfig:
    """本地运行时配置。"""

    workspace_root: str = "."
    allowed_directories: list[str] = field(default_factory=lambda: [".", "/tmp"])
    enable_path_validation: bool = True
    default_timeout: int = 300
    shell_executable: str = "/bin/bash"


@dataclass
class SecurityConfig:
    """代码执行安全配置。"""

    max_execution_time: int = 300
    max_code_length: int = 10000
    max_file_size: int = 10485760
    enable_code_validation: bool = True
    allowed_imports: list[str] = field(
        default_factory=lambda: [
            "os",
            "sys",
            "json",
            "asyncio",
            "pathlib",
            "datetime",
            "re",
            "math",
            "typing",
        ]
    )
    blocked_patterns: list[str] = field(
        default_factory=lambda: [
            "eval(",
            "exec(",
            "__import__",
            "subprocess.call",
            "subprocess.Popen",
            "os.system",
        ]
    )


@dataclass
class LoggingConfig:
    """日志配置。"""

    level: str = "INFO"
    file: str = "logs/hnk_agent.log"


@dataclass
class CoreConfig:
    """核心基础设施配置。"""

    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    config_file_dir: Path | None = None
