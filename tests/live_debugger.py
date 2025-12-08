import weave

def adder(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


def multiplier(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


def liner(m: float, b: float, x: float) -> float:
    """Calculate y = mx + b."""
    return adder(multiplier(m, x), b)




if __name__ == "__main__":
    debugger = weave.Debugger()
    debugger.add_callable(adder)
    debugger.add_callable(multiplier)
    debugger.add_callable(liner)
    debugger.start()