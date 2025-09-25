
def signed8(value):
    if value > 127:
        value -= 256
    return value
