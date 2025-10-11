from Emulation import Emulation
from customTypes import *
import datetime
from pathlib import Path

# Using pathlib for more robust path handling

def main():
    rompath = "6_Instructions2.nes"
    emu_instance = Emulation(rompath, debug = True)
    timenow = datetime.datetime.now()
    timeform = "%Y-%m-%d.%H.%M.%S"
    file = Path(f"logs/{timenow.strftime(timeform)}.csv")
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", newline="") as log:
        emu_instance.run_emu(log)
        junk = emu_instance.addSpace
        toprint = []
        for value in emu_instance.addSpace[0x10:0x1D]:
            toprint.append(value)
        output = list(map(hex, toprint))
        print(output)
        pass


if __name__ == '__main__':
    main()
