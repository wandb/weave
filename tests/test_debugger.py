import weave

def my_func(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    debugger = weave.Debugger(my_func)
    debugger.start()