
class Emulation:
    def __init__(self, filepath):
        # initialize path to rom, relevant registers and flags
        self.rompath = filepath
        self.pgmctr = 0x00
        self.regA = 0x00
        self.regX = 0x00
        self.regY = 0x00
        self.opcode = 0
        self.vdebt = 0
        self.halt = False
        self.flag_carry = False
        self.flag_Zero = False
        self.flag_InterruptDisable = False
        self.flag_Decimal = False
        self.flag_Overflow = False
        self.flag_Negative = False

        # initialize ram
        self.addSpace = [0xff] * 0x8000

        # Initialize rom
        with open(self.rompath, "rb") as data:
            self.header = (chunk for chunk in data.read(0x10))
            self.addSpace += (chunk for chunk in data.read())

        # Move the Program Counter to correct space (we have to do a little math to convert to little endian)
        self.pgmctr = self.addSpace[0xFFFC] + self.addSpace[0xFFFD]*256

    def run_emu(self):
        self.flag_InterruptDisable = True
        while not self.halt:
            self.opcode = self.addSpace[self.pgmctr]
            print(self.opcode, self.pgmctr, self.regA, self.addSpace[0x0])
            self.pgmctr += 0x1
            self.op()

    def read(self, address, mirror=True):
        while 0x1FFF > address >= 0x800 and mirror:
            address -= 0x800
        rvalue = self.addSpace[address]
        self.flag_Zero = False
        self.flag_Negative = False
        if rvalue == 0:
            self.flag_Zero = True
        elif rvalue > 127:
            self.flag_Negative = True
        return self.addSpace[address]

    def write(self, address, data):
        if address > 0x800:
            raise MemoryError(f"Attempted to write to invalid memory address {address} at line {self.pgmctr}")
        else:
            self.addSpace[address] = data

    def op(self):
        match self.opcode:
            case 0x84: # STY Zero Page
                self.write(self.read(self.pgmctr), self.regY); self.vdebt += 3
            case 0x85: # STA Zero Page
                self.write(self.read(self.pgmctr), self.regA); self.vdebt += 3
            case 0x86: # STX Zero Page
                self.write(self.read(self.pgmctr), self.regX); self.vdebt += 3
            case 0x8C: # STY Absolute
                tlow = self.read(self.pgmctr); self.pgmctr += 1
                self.write((tlow+self.read(self.pgmctr)*256), self.regY); self.vdebt += 4
            case 0x8D: # STA absolute
                tlow = self.read(self.pgmctr); self.pgmctr += 1
                self.write((tlow+self.read(self.pgmctr)*256), self.regA); self.vdebt += 4
            case 0x8E: # STX Absolute
                tlow = self.read(self.pgmctr); self.pgmctr += 1
                self.write((tlow+self.read(self.pgmctr)*256), self.regX); self.vdebt += 4
            case 0x02:  # HTL
                self.halt = True
            case 0xA0:  # immediate Y
                self.regY = self.read(self.pgmctr); self.vdebt += 2
            case 0xA2:  # immediate X
                self.regX = self.read(self.pgmctr); self.vdebt += 2
            case 0xA5: # LDA Zero Page
                self.regA = self.read(self.pgmctr); self.vdebt += 3 # Needs confirm
            case 0xA9:  # immediate A
                self.regA = self.read(self.pgmctr); self.vdebt += 2
            case 0xAD: # LDA Absolute
                tlow = self.read(self.pgmctr); self.pgmctr += 1
                self.regA = self.read((tlow+self.read(self.pgmctr)*256)); self.vdebt += 4 # Needs confirm
        self.pgmctr += 1
