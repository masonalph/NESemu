from Emulation import Emulation
from customTypes import *
def main():

    filepath = "testfile.nes"
    emu_instance = Emulation(filepath, debug=True)
    emu_instance.run_emu()

    # $69 Immediate addition test

if __name__ == '__main__':
    main()


