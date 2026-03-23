"""本地工作区管理。"""

from __future__ import annotations

from pathlib import Path


class LocalWorkspace:
    """本地运行时工作区。

    负责：
    - 规范化路径
    - 校验路径权限
    - 维护基础目录布局
    """

    def __init__(
        self,
        root_dir: str | Path,
        allowed_directories: list[str | Path] | None = None,
        enable_path_validation: bool = True,
    ) -> None:
        """初始化工作区。"""
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.enable_path_validation = enable_path_validation

        raw_allowed = allowed_directories or [self.root_dir, Path("/tmp")]
        normalized_allowed = [
            Path(directory).expanduser().resolve()
            for directory in raw_allowed
        ]

        # 无论外部是否显式传入，工作区根目录都应该始终允许访问。
        if self.root_dir not in normalized_allowed:
            normalized_allowed.insert(0, self.root_dir)

        self.allowed_directories = normalized_allowed

    @property
    def code_dir(self) -> Path:
        """返回代码缓存目录。"""
        return self.root_dir / "code"

    @property
    def data_dir(self) -> Path:
        """返回数据目录。"""
        return self.root_dir / "data"

    @property
    def results_dir(self) -> Path:
        """返回结果目录。"""
        return self.root_dir / "results"

    @property
    def tools_dir(self) -> Path:
        """返回工具目录。"""
        return self.root_dir / "tools"

    def ensure_layout(self) -> None:
        """确保基础目录结构存在。"""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.code_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.tools_dir.mkdir(parents=True, exist_ok=True)

    def normalize_path(self, path: str | None) -> str:
        """把虚拟路径或相对路径转换为真实绝对路径。"""
        if path in (None, "", ".", "/"):
            return str(self.root_dir)

        raw_path = str(path).strip()

        for allowed_dir in self.allowed_directories:
            allowed_str = str(allowed_dir)
            if raw_path == allowed_str or raw_path.startswith(allowed_str + "/"):
                return str(Path(raw_path).expanduser().resolve(strict=False))

        if raw_path.startswith("/"):
            normalized = self.root_dir / raw_path.lstrip("/")
            return str(normalized.resolve(strict=False))

        normalized = self.root_dir / raw_path
        return str(normalized.resolve(strict=False))

    def virtualize_path(self, path: str) -> str:
        """把真实路径转成对 agent 更友好的展示路径。"""
        normalized = Path(path).expanduser().resolve(strict=False)

        try:
            relative = normalized.relative_to(self.root_dir)
        except ValueError:
            return str(normalized)

        relative_str = str(relative)
        if relative_str in ("", "."):
            return "/"
        return f"/{relative_str}"

    def validate_path(self, file_path: str) -> bool:
        """校验路径是否位于允许访问的目录下。"""
        if not self.enable_path_validation:
            return True

        normalized = Path(self.normalize_path(file_path)).resolve(strict=False)
        for allowed_dir in self.allowed_directories:
            if normalized == allowed_dir or str(normalized).startswith(str(allowed_dir) + "/"):
                return True
        return False

    def validate_and_normalize_path(self, path: str | None) -> tuple[str, str | None]:
        """规范化路径并返回错误信息。"""
        normalized = self.normalize_path(path)
        if not self.validate_path(normalized):
            return normalized, f"Access denied: {path} is not in allowed directories"
        return normalized, None
