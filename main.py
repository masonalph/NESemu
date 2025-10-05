from Emulation import Emulation
from customTypes import *
import csv

def main():
    filepath = "testfile.nes"
    emu_instance = Emulation(filepath, debug=True)
    emu_instance.run_emu()
    logs = emu_instance.logger
    for i in logs:
        print(f"Program Counter {hex(i['Program Counter'])} \n"
              f"Op: {hex(i['Op'])} RegA: {hex(i['RegA'])} RegX: {hex(i['RegX'])} RegY: {hex(i['RegY'])}")

if __name__ == '__main__':
    main()


