from typing import Any, Callable, Literal, Tuple, TypeVar

_CacheKey = Tuple[str, str, Tuple[Any, ...]]
_CacheValue = Tuple[Any, float]
_FuncT = TypeVar('_FuncT', bound=Callable[..., Any])
_CacheScope = Literal["organization", "user", "global"]
