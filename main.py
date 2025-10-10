from Emulation import Emulation
from customTypes import *
import datetime
from pathlib import Path

# Using pathlib for more robust path handling

def main():
    rompath = "5_Instructions1.nes"
    emu_instance = Emulation(rompath, debug = True)
    timenow = datetime.datetime.now()
    timeform = "%Y-%m-%d.%H.%M.%S"
    file = Path(f"logs/{timenow.strftime(timeform)}.csv")
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", newline="") as log:
        emu_instance.run_emu(log)
        junk = emu_instance.addSpace
        print(emu_instance.addSpace[0 : 0x000C])
        pass


if __name__ == '__main__':
    main()
