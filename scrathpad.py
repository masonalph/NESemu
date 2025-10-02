for a in range (0,255):
    out = (a%128)*2
    assert out <255, f"{a} resulted in out"
    print(out)