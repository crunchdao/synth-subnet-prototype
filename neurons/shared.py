import functools
import time
import sys


def async_timeit(params: list):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            kwargs.update(zip(
                func.__code__.co_varnames[:func.__code__.co_argcount],
                args
            ))

            start_time = time.perf_counter()
            try:
                return await func(**kwargs)
            finally:
                end_time = time.perf_counter()
                total_time = end_time - start_time

                if params is not None:
                    arguments = ", ".join([
                        str(value) if name in params else "..."
                        for name, value in kwargs.items()
                    ])

                    print(f'[debug] {func.__name__}({arguments}) took {total_time:.4f} seconds', file=sys.stderr)
                else:
                    print(f'[debug] {func.__name__} took {total_time:.4f} seconds', file=sys.stderr)

        return wrapper

    return decorator
