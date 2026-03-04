"""Retry utility with exponential backoff using tenacity."""

import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    retry,
)

from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class RetryableError(Exception):
    """Error that can be retried."""

    pass


def async_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """
    Decorator for async functions with retry logic.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        retryable_exceptions: Tuple of exceptions to retry on

    Returns:
        Decorated function with retry logic
    """
    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            attempt = 0
            last_exception: Exception | None = None

            async for attempt_state in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(retryable_exceptions),
                reraise=True,
            ):
                with attempt_state:
                    attempt += 1
                    try:
                        return await func(*args, **kwargs)
                    except retryable_exceptions as e:
                        last_exception = e
                        if attempt < max_attempts:
                            logger.warning(
                                f"Retry attempt {attempt}/{max_attempts}",
                                function=func.__name__,
                                error=str(e),
                            )
                        raise

            # This should not be reached
            if last_exception:
                raise last_exception
            raise RetryError(None)  # type: ignore

        return wrapper
    return decorator


async def with_retry(
    operation: Callable[[], Any],
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """
    Execute an async operation with retry logic.

    Args:
        operation: Async callable to execute
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        retryable_exceptions: Tuple of exceptions to retry on
        on_retry: Callback function called on each retry

    Returns:
        Result of the operation

    Raises:
        RetryError: If all retry attempts fail
    """
    if retryable_exceptions is None:
        retryable_exceptions = (Exception,)

    attempt = 0
    last_exception: Exception | None = None

    async for attempt_state in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(retryable_exceptions),
        reraise=True,
    ):
        with attempt_state:
            attempt += 1
            try:
                result = await operation()
                return result
            except retryable_exceptions as e:
                last_exception = e
                if attempt < max_attempts:
                    logger.warning(
                        "Operation failed, retrying",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error=str(e),
                    )
                    if on_retry:
                        on_retry(attempt, e)
                raise

    # This should not be reached, but handle it gracefully
    if last_exception:
        raise last_exception
    raise RetryError(None)  # type: ignore


def is_retryable_http_error(status_code: int) -> bool:
    """Check if HTTP status code is retryable."""
    return status_code in {408, 429, 500, 502, 503, 504}


def calculate_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """Calculate exponential backoff delay."""
    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
    return delay


async def sleep(seconds: float) -> None:
    """Async sleep wrapper."""
    await asyncio.sleep(seconds)
