
def signed8(value):
    if value > 127:
        value -= 256
    return value


def badd(a, b, carry=False):
    print(f"adding{a} and {b}")
    tempa = bin(a)[2:]; tempb= bin(b)[2:]
    while len(tempa) < 8:
        tempa = "0"+tempa
    while len(tempb) < 8:
        tempb = "0"+tempb
    tempout = ""
    for bit in range(0,8):
        tempresult = int(tempa[bit]) + int(tempb[bit]) + carry
        match tempresult:
            case 0:
                carry = False
                tempout += "0"
            case 1:
                carry = False
                tempout += "1"
            case 2:
                carry = True
                tempout += "0"
            case 3:
                carry = True
                tempout += "1"
    print(tempout)
    print(int("0b"+tempout, 2))
    return int(tempout,2), carry
