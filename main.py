from Emulation import Emulation

def main():
    halt = False
    filepath = "2_ReadWrite.nes"
    emu_instance = Emulation(filepath)
    emu_instance.run_emu()

if __name__ == '__main__':
    main()


