import timeit

modulus = """for x in range(0, 255):
    if x > 127:
        y = True
    else:
        y = False
        """

branching = """for x in range (0,255):
    y = x > 127"""

print(f"Modulus time = {timeit.timeit(stmt = modulus, number = 1000000)}")
print(f"Branching time = {timeit.timeit(stmt = branching, number = 1000000)}")