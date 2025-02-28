import collections.abc
import modal._partial_function
import modal.functions
import modal_proto.api_pb2
import typing

class PartialFunction(
    typing.Generic[
        modal._partial_function.P, modal._partial_function.ReturnType, modal._partial_function.OriginalReturnType
    ]
):
    raw_f: collections.abc.Callable[modal._partial_function.P, modal._partial_function.ReturnType]
    flags: modal._partial_function._PartialFunctionFlags
    webhook_config: typing.Optional[modal_proto.api_pb2.WebhookConfig]
    is_generator: bool
    keep_warm: typing.Optional[int]
    batch_max_size: typing.Optional[int]
    batch_wait_ms: typing.Optional[int]
    force_build: bool
    cluster_size: typing.Optional[int]
    build_timeout: typing.Optional[int]

    def __init__(
        self,
        raw_f: collections.abc.Callable[modal._partial_function.P, modal._partial_function.ReturnType],
        flags: modal._partial_function._PartialFunctionFlags,
        webhook_config: typing.Optional[modal_proto.api_pb2.WebhookConfig] = None,
        is_generator: typing.Optional[bool] = None,
        keep_warm: typing.Optional[int] = None,
        batch_max_size: typing.Optional[int] = None,
        batch_wait_ms: typing.Optional[int] = None,
        cluster_size: typing.Optional[int] = None,
        force_build: bool = False,
        build_timeout: typing.Optional[int] = None,
    ): ...
    def _get_raw_f(self) -> collections.abc.Callable[modal._partial_function.P, modal._partial_function.ReturnType]: ...
    def _is_web_endpoint(self) -> bool: ...
    def __get__(
        self, obj, objtype=None
    ) -> modal.functions.Function[
        modal._partial_function.P, modal._partial_function.ReturnType, modal._partial_function.OriginalReturnType
    ]: ...
    def __del__(self): ...
    def add_flags(self, flags) -> PartialFunction: ...

def method(
    _warn_parentheses_missing=None,
    *,
    is_generator: typing.Optional[bool] = None,
    keep_warm: typing.Optional[int] = None,
) -> modal._partial_function._MethodDecoratorType: ...
def web_endpoint(
    _warn_parentheses_missing=None,
    *,
    method: str = "GET",
    label: typing.Optional[str] = None,
    docs: bool = False,
    custom_domains: typing.Optional[collections.abc.Iterable[str]] = None,
    requires_proxy_auth: bool = False,
    wait_for_response: bool = True,
) -> collections.abc.Callable[
    [collections.abc.Callable[modal._partial_function.P, modal._partial_function.ReturnType]],
    PartialFunction[modal._partial_function.P, modal._partial_function.ReturnType, modal._partial_function.ReturnType],
]: ...
def asgi_app(
    _warn_parentheses_missing=None,
    *,
    label: typing.Optional[str] = None,
    custom_domains: typing.Optional[collections.abc.Iterable[str]] = None,
    requires_proxy_auth: bool = False,
    wait_for_response: bool = True,
) -> collections.abc.Callable[[collections.abc.Callable[..., typing.Any]], PartialFunction]: ...
def wsgi_app(
    _warn_parentheses_missing=None,
    *,
    label: typing.Optional[str] = None,
    custom_domains: typing.Optional[collections.abc.Iterable[str]] = None,
    requires_proxy_auth: bool = False,
    wait_for_response: bool = True,
) -> collections.abc.Callable[[collections.abc.Callable[..., typing.Any]], PartialFunction]: ...
def web_server(
    port: int,
    *,
    startup_timeout: float = 5.0,
    label: typing.Optional[str] = None,
    custom_domains: typing.Optional[collections.abc.Iterable[str]] = None,
    requires_proxy_auth: bool = False,
) -> collections.abc.Callable[[collections.abc.Callable[..., typing.Any]], PartialFunction]: ...
def build(
    _warn_parentheses_missing=None, *, force: bool = False, timeout: int = 86400
) -> collections.abc.Callable[
    [typing.Union[collections.abc.Callable[[typing.Any], typing.Any], PartialFunction]], PartialFunction
]: ...
def enter(
    _warn_parentheses_missing=None, *, snap: bool = False
) -> collections.abc.Callable[
    [typing.Union[collections.abc.Callable[[typing.Any], typing.Any], PartialFunction]], PartialFunction
]: ...
def exit(
    _warn_parentheses_missing=None,
) -> collections.abc.Callable[
    [
        typing.Union[
            collections.abc.Callable[
                [typing.Any, typing.Optional[type[BaseException]], typing.Optional[BaseException], typing.Any],
                typing.Any,
            ],
            collections.abc.Callable[[typing.Any], typing.Any],
        ]
    ],
    PartialFunction,
]: ...
def batched(
    _warn_parentheses_missing=None, *, max_batch_size: int, wait_ms: int
) -> collections.abc.Callable[[collections.abc.Callable[..., typing.Any]], PartialFunction]: ...
