from abc import ABC, abstractmethod
from functools import wraps
from asyncio import iscoroutinefunction
from inspect import signature, isgeneratorfunction
from typing import Callable, Dict, List, Tuple, Union
from types import CoroutineType
from robyn.robyn import FunctionInfo

from robyn.ws import WS

Route = Tuple[str, str, Callable, bool, int, bool]
MiddlewareRoute = Tuple[str, str, Callable, bool, int]


class BaseRouter(ABC):
    @abstractmethod
    def add_route(*args) -> Union[Callable, CoroutineType, WS]:
        ...


class Router(BaseRouter):
    def __init__(self) -> None:
        super().__init__()
        self.routes = []

    def _format_response(self, res):
        # handle file handlers
        response = {}
        if type(res) == dict:
            if "status_code" not in res:
                res["status_code"] = "200"
                response = res
            else:
                if type(res["status_code"]) == int:
                    res["status_code"] = str(res["status_code"])

                response = {"status_code": "200", "body": res["body"], **res}
        else:
            response = {"status_code": "200", "body": res, "type": "text"}

        return response

    def add_route(
        self, route_type: str, endpoint: str, handler: Callable, is_const: bool
    ) -> Union[Callable, CoroutineType]:
        @wraps(handler)
        async def async_inner_handler(*args):
            response = self._format_response(await handler(*args))
            return response

        @wraps(handler)
        def inner_handler(*args):
            response = self._format_response(handler(*args))
            return response

        number_of_params = len(signature(handler).parameters)
        is_cortoutine = iscoroutinefunction(handler)
        is_generator = isgeneratorfunction(handler)

        if is_cortoutine and not is_generator:
            function = FunctionInfo(async_inner_handler, "async_function", number_of_params)
            self.routes.append((route_type, endpoint, function, is_const))
            return async_inner_handler
        elif not is_cortoutine and not is_generator:
            function = FunctionInfo(inner_handler, "sync_function", number_of_params)
            self.routes.append((route_type, endpoint, function, is_const))
            return inner_handler
        elif not is_cortoutine and is_generator:
            function = FunctionInfo(inner_handler, "sync_generator", number_of_params)
            self.routes.append((route_type, endpoint, function, is_const))
            return inner_handler
        else:
            raise Exception("Async generator functions are not supported at the moment.")

    def get_routes(self) -> List[Route]:
        return self.routes


class MiddlewareRouter(BaseRouter):
    def __init__(self) -> None:
        super().__init__()
        # TODO: Need to add types for this array
        self.routes = []

    def add_route(self, route_type: str, endpoint: str, handler: Callable) -> Callable:
        number_of_params = len(signature(handler).parameters)
        is_cortoutine = iscoroutinefunction(handler)
        is_generator = isgeneratorfunction(handler)

        if is_cortoutine and not is_generator:
            function = FunctionInfo(handler, "sync_function", number_of_params)
            self.routes.append((route_type, endpoint, function))
        elif not is_cortoutine and not is_generator:
            function = FunctionInfo(handler, "async_function", number_of_params)
            self.routes.append((route_type, endpoint, function))
        elif not is_cortoutine and is_generator:
            function = FunctionInfo(handler, "sync_generator", number_of_params)
            self.routes.append((route_type, endpoint, function))
        else:
            raise Exception("Async generator functions are not supported at the moment.")

        return handler

    def get_routes(self) -> List[Route]:
        return self.routes
    # These inner function is basically a wrapper arround the closure(decorator)
    # being returned.
    # It takes in a handler and converts it in into a closure
    # and returns the arguments.
    # Arguments are returned as they could be modified by the middlewares.
    def add_after_request(self, endpoint: str) -> Callable[..., None]:
        def inner(handler):
            @wraps(handler)
            async def async_inner_handler(*args):
                await handler(*args)
                return args

            @wraps(handler)
            def inner_handler(*args):
                handler(*args)
                return args

            if iscoroutinefunction(handler):
                self.add_route("AFTER_REQUEST", endpoint, async_inner_handler)
            else:
                self.add_route("AFTER_REQUEST", endpoint, inner_handler)

        return inner

    def add_before_request(self, endpoint: str) -> Callable[..., None]:
        def inner(handler):
            @wraps(handler)
            async def async_inner_handler(*args):
                await handler(*args)
                return args

            @wraps(handler)
            def inner_handler(*args):
                handler(*args)
                return args

            if iscoroutinefunction(handler):
                self.add_route("BEFORE_REQUEST", endpoint, async_inner_handler)
            else:
                self.add_route("BEFORE_REQUEST", endpoint, inner_handler)

        return inner

    def get_routes(self) -> List[MiddlewareRoute]:
        return self.routes


class WebSocketRouter(BaseRouter):
    def __init__(self) -> None:
        super().__init__()
        self.routes = {}

    def add_route(self, endpoint: str, web_socket: WS) -> None:
        self.routes[endpoint] = web_socket

    def get_routes(self) -> Dict[str, WS]:
        return self.routes
