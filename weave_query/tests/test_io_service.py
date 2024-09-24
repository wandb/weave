import asyncio

import pytest

from weave.legacy.weave import filesystem, io_service


@pytest.mark.timeout(10)
@pytest.mark.asyncio
@pytest.mark.parametrize("process", [True, False])
async def test_io_service_async_client(io_server_factory, process):
    server: io_service.Server = io_server_factory(process)
    client = io_service.AsyncClient(
        server=server,
    )

    loop = asyncio.get_running_loop()

    results = []
    tasks = set()
    async with client.connect() as conn:
        for _ in range(10):
            task = loop.create_task(conn.sleep(0.1))
            tasks.add(task)

            def task_done_callback(fut):
                results.append(fut.result())

            task.add_done_callback(task_done_callback)
        await asyncio.wait(tasks)

    assert len(results) == 10

    for result in results:
        assert result == 0.1

    assert not conn.connected
    assert len(server.client_response_queues) == 0


@pytest.mark.timeout(10)
@pytest.mark.asyncio
@pytest.mark.parametrize("process", [True, False])
async def test_io_service_sync_client(io_server_factory, process):
    server: io_service.Server = io_server_factory(process)
    fs = filesystem.get_filesystem()
    client = io_service.SyncClient(
        server=server,
        fs=fs,
    )

    results = []
    for _ in range(10):
        results.append(client.sleep(0.1))

    assert len(results) == 10

    # if serial, this should be greater than 1 second (10 * 0.1)
    # if executed concurrently, this should be between 0.1 and 0.2 (0.1 + overhead)
    for result in results:
        assert result == 0.1

    assert len(server.client_response_queues) == 0
