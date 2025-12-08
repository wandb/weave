import weave

def adder(a: float, b: float) -> float:
    return a + b

def multiplier(a: float, b: float) -> float:
    return a * b

def liner(m: float, b: float, x: float) -> float:
    return adder(multiplier(m, x), b)






if __name__ == "__main__":
    debugger = weave.Debugger()
    debugger.add_callable(adder)
    debugger.add_callable(multiplier)
    debugger.add_callable(liner)
    debugger.start()