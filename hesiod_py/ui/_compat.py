'''Compatibility utilities for third-party dependencies.'''

from __future__ import annotations

import re
import sys
import types
from itertools import zip_longest

__all__ = ["ensure_distutils"]


def ensure_distutils() -> None:
    """Ensure a minimal ``distutils.version`` implementation is available.

    NodeGraphQt relies on :mod:`distutils`, which was removed in Python 3.12.
    This shim provides a small subset sufficient for their LooseVersion usage.
    """
    try:
        import distutils.version  # type: ignore[import-not-found]  # noqa: F401
    except ModuleNotFoundError:
        version_module = types.ModuleType("distutils.version")

        class LooseVersion:
            """Small subset of distutils.version.LooseVersion."""

            _split_re = re.compile(r"[._-]")

            def __init__(self, version: object) -> None:
                self.vstring = str(version)
                self.version = self._parse(self.vstring)

            @classmethod
            def _parse(cls, value: str) -> list[object]:
                parts: list[object] = []
                for token in cls._split_re.split(value):
                    if not token:
                        continue
                    if token.isdigit():
                        parts.append(int(token))
                    else:
                        parts.append(token)
                return parts

            def _compare(self, other: object) -> int:
                if not isinstance(other, LooseVersion):
                    other = LooseVersion(other)
                for left, right in zip_longest(self.version, other.version, fillvalue=0):
                    if isinstance(left, int) and isinstance(right, int):
                        if left != right:
                            return (left > right) - (left < right)
                    else:
                        left_str = str(left)
                        right_str = str(right)
                        if left_str != right_str:
                            return (left_str > right_str) - (left_str < right_str)
                return 0

            def __repr__(self) -> str:
                return f"LooseVersion('{self.vstring}')"

            def __str__(self) -> str:
                return self.vstring

            def __lt__(self, other: object) -> bool:
                return self._compare(other) < 0

            def __le__(self, other: object) -> bool:
                return self._compare(other) <= 0

            def __eq__(self, other: object) -> bool:
                return self._compare(other) == 0

            def __ne__(self, other: object) -> bool:
                return self._compare(other) != 0

            def __gt__(self, other: object) -> bool:
                return self._compare(other) > 0

            def __ge__(self, other: object) -> bool:
                return self._compare(other) >= 0

        version_module.LooseVersion = LooseVersion  # type: ignore[attr-defined]

        distutils_module = types.ModuleType("distutils")
        distutils_module.version = version_module  # type: ignore[attr-defined]

        sys.modules.setdefault("distutils", distutils_module)
        sys.modules.setdefault("distutils.version", version_module)
    else:
        return None
