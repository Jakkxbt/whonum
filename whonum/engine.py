import asyncio
import httpx


async def scan(intel: dict, modules=None, concurrency: int = 6, timeout: int = 12):
    from .modules import ALL_MODULES
    if modules is None:
        modules = ALL_MODULES

    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=5)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, limits=limits) as client:
        async def run_one(mod):
            async with sem:
                return await mod(client, intel)

        return await asyncio.gather(*[run_one(m) for m in modules])


def scan_sync(intel: dict, **kwargs):
    return asyncio.run(scan(intel, **kwargs))
