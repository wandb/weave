def test_import_is_fast():
    import time

    start_time = time.time()
    import weave  # noqa: F401

    end_time = time.time() - start_time

    assert end_time < 2, f"Import took {end_time} seconds"
