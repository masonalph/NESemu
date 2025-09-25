from Emulation import Emulation
from customTypes import *
def main():

    filepath = "4_TheStack.nes"
    emu_instance = Emulation(filepath, debug=True)
    emu_instance.run_emu()


if __name__ == '__main__':
    main()


