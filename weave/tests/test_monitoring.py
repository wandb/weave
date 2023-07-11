import time
from weave import monitoring


def test_monitoring():
    @monitoring.monitor()
    def example(a, b):
        return a + b

    for i in range(10):
        for j in range(10):
            time.sleep(1)
            example(i, j)

    assert False
