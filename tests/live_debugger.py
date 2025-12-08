import weave

@weave.op()
def adder(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@weave.op()
def multiplier(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@weave.op()
def liner(m: float, b: float, x: float) -> float:
    """Calculate y = mx + b."""
    return adder(multiplier(m, x), b)




if __name__ == "__main__":
    weave.init("live_debugger")
    debugger = weave.Debugger()
    debugger.add_callable(adder)
    debugger.add_callable(multiplier)
    debugger.add_callable(liner)
    debugger.start()