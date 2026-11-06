import asyncio


def walk_tree(node):
    return walk_tree(node + 1)


async def fetch_report():
    await asyncio.sleep(1)


async def build_report():
    return await asyncio.wait_for(fetch_report(), timeout=0.01)


def run_report():
    return asyncio.run(build_report())
