from typing import Any, Callable, Tuple, TypeVar, Union

_CacheKey = Tuple[str, str, Tuple[Any, ...]]
_CacheValue = Tuple[Any, float]
_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])
_CacheScope = Union[str, Tuple[str, ...]]
