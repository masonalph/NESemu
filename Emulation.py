from customTypes import *
import math

class Emulation:
    def __init__(self, filepath, debug=False):
        # initialize path to rom, relevant registers and flags
        self.debug = debug
        self.rompath = filepath
        self.pgmctr = 0x00
        self.regA = 0x00
        self.regX = 0x00
        self.regY = 0x00
        self.opcode = 0
        self.vdebt = 0
        self.halt = False
        self.flag_Carry = False
        self.flag_Zero = False
        self.flag_InterruptDisable = False
        self.flag_Decimal = False
        self.flag_Overflow = False
        self.flag_Negative = False
        self.stackptr = 0xFD

        # initialize ram
        self.addSpace = [0xff] * 0x8000

        # Initialize rom
        with open(self.rompath, "rb") as data:
            self.header = (chunk for chunk in data.read(0x10))
            self.addSpace += (chunk for chunk in data.read())

        # Move the Program Counter to correct space (we have to do a little math to convert to little endian)

        if debug:
            self.pgmctr = 0x8000
        else:
            self.pgmctr = self.addSpace[0xFFFC] + self.addSpace[0xFFFD] * 256

    def push(self, value):
        self.write(0x100 + self.stackptr, value)
        self.stackptr -= 1

    def pull(self):
        if self.stackptr == 0xFF:
            self.stackptr = 0x00
        else:
            self.stackptr += 1
        return self.read(0x100 + self.stackptr)

    def run_emu(self):
        self.flag_InterruptDisable = True
        while not self.halt:
            self.opcode = self.addSpace[self.pgmctr]
            self.pgmctr += 0x1
            print(self.regA)
            if self.debug:
                print("op:" + hex(self.opcode),  "pgmctr:" + hex(self.pgmctr),
                      "regA:" + hex(self.regA), "0x0:" + hex(self.addSpace[0x0]))
            self.op()

    def read(self, address=-1, mirror=True):
        if address == -1:
            address = self.pgmctr
        while 0x1FFF > address >= 0x800 and mirror:
            address -= 0x800
        return self.addSpace[address]

    def write(self, address, data):
        if address > 0x800:
            raise MemoryError(f"Attempted to write to invalid memory address {address} at line {self.pgmctr}")
        else:
            self.addSpace[address] = data

    def flagnum(self, register, negative=True, zero=True):
        if negative:
            if register > 127:
                self.flag_Negative = True
            else:
                self.flag_Negative = False
        if zero:
            if register == 0:
                self.flag_Zero = True
            else:
                self.flag_Zero = False

    def op(self):
        match self.opcode:
            case 0x02:  # HTL
                self.halt = True
            case 0x10: # Branch on Plus
                if not self.flag_Negative:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if temppg % 256 != self.pgmctr % 256:
                        self.vdebt += 1  # Branch takes extra cycle if crossing page boundary
                    self.vdebt += 1  # Takes 1 additional cycles if nonzero
                self.vdebt += 2  # Takes 2 cycles no matter what
            case 0x18: # Clear Carry
                self.flag_Carry = False; self.vdebt += 2
                return
            case 0x20: # Jump to Subroutine
                tlow = self.read(); self.pgmctr += 1
                thigh = self.read()
                self.push(math.floor(self.pgmctr/256)); self.push(self.pgmctr % 256)
                self.pgmctr = (tlow+thigh*256); self.vdebt += 6
                return
            case 0x30:  # Branch on Minus.
                if self.flag_Negative:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if temppg % 256 != self.pgmctr % 256:
                        self.vdebt += 1  # Branch takes extra cycle if crossing page boundary
                    self.vdebt += 1  # Takes 1 additional cycles if nonzero
                self.vdebt += 2  # Takes 2 cycles no matter what
            case 0x38: # Set Carry
                self.flag_Carry = True; self.vdebt += 2
                return
            case 0x48: # Push Accumulator
                self.push(self.regA); self.vdebt += 3
                return
            case 0x50:  # Branch on not Overflow
                if not self.flag_Overflow:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if temppg % 256 != self.pgmctr % 256:
                        self.vdebt += 1  # Branch takes extra cycle if crossing page boundary
                    self.vdebt += 1  # Takes 1 additional cycles if nonzero
                self.vdebt += 2  # Takes 2 cycles no matter what
            case 0x58: # Clear Interrupt-Disable
                self.flag_InterruptDisable = False; self.vdebt += 2
                return
            case 0x60: # Return from Subroutine
                tlow = self.pull(); self.pgmctr = (tlow+self.pull()*256); self.vdebt += 6
            case 0x68: # Pull Accumulator
                self.regA = self.pull(); self.vdebt += 4
                self.flagnum(self.regA)
                return
            case 0x69: # Add to accumulator immediate
                # Math using BCD if Decimal flag is high
                if self.flag_Decimal:
                    tcarry = 0
                    tlowa = self.regA % 16; thigha = math.floor(self.regA / 16)
                    tlowmem = self.read() % 16; thighmem = math.floor(self.read() / 16)
                    resultlow = self.flag_Carry + tlowa + tlowmem
                    self.flag_Carry = False
                    if resultlow > 10:
                        resultlow -= 10
                        tcarry = 1
                    resulthigh = thigha + thighmem + tcarry
                    if resulthigh > 10:
                        resulthigh -= 10
                        self.flag_Carry = True
                    self.regA = resulthigh*16 + resultlow
                    if self.regA == 0:
                        self.flag_Zero = True
                # If Decimal flag off, treat the numbers as either signed or unsigned
                else:
                    tempval = self.regA + self.read() + self.flag_Carry
                    if tempval > 256:
                        tempval -= 256; self.flag_Carry = True
                    elif tempval == 0 and not self.flag_Carry:
                        self.flag_Zero = True
                self.vdebt += 2

            case 0x70:  # Branch on Overflow
                if self.flag_Overflow:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if temppg % 256 != self.pgmctr % 256:
                        self.vdebt += 1  # Branch takes extra cycle if crossing page boundary
                    self.vdebt += 1  # Takes 1 additional cycles if nonzero
                self.vdebt += 2  # Takes 2 cycles no matter what
            case 0x78: # Set Interrupt-Disable
                self.flag_InterruptDisable = True; self.vdebt += 2
                return
            case 0x84: # STY Zero Page
                self.write(self.read(), self.regY); self.vdebt += 3
            case 0x85: # STA Zero Page
                self.write(self.read(), self.regA); self.vdebt += 3
            case 0x86: # STX Zero Page
                self.write(self.read(), self.regX); self.vdebt += 3
            case 0x8C: # STY Absolute
                tlow = self.read(); self.pgmctr += 1
                self.write((tlow+self.read()*256), self.regY); self.vdebt += 4
            case 0x8D: # STA absolute
                tlow = self.read(); self.pgmctr += 1
                self.write((tlow+self.read()*256), self.regA); self.vdebt += 4
            case 0x8E: # STX Absolute
                tlow = self.read(); self.pgmctr += 1
                self.write((tlow+self.read()*256), self.regX); self.vdebt += 4
            case 0x90: # Branch on not Carry
                if not self.flag_Carry:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if temppg % 256 != self.pgmctr % 256:
                        self.vdebt += 1  # Branch takes extra cycle if crossing page boundary
                    self.vdebt += 1  # Takes 1 additional cycles if nonzero
                self.vdebt += 2  # Takes 2 cycles no matter what
            case 0xA0:  # immediate Y
                self.regY = self.read(); self.vdebt += 2
                self.flagnum(self.regY)
            case 0xA2:  # immediate X
                self.regX = self.read(); self.vdebt += 2
                self.flagnum(self.regX)
            case 0xA5: # LDA Zero Page
                self.regA = self.read(); self.vdebt += 2
                self.flagnum(self.regA)
            case 0xA9:  # immediate A
                self.regA = self.read(); self.vdebt += 2
                self.flagnum(self.regA)
            case 0xAD: # LDA Absolute
                tlow = self.read(self.pgmctr); self.pgmctr += 1
                self.regA = self.read((tlow+self.read(self.pgmctr)*256)); self.vdebt += 4
                self.flagnum(self.regA)
                # TODO Extra cycle if page boundary crossed
            case 0xB8: # Clear Overflow
                self.flag_Overflow = False; self.vdebt += 2
                return
            case 0xD8: # Clear Decimal Flag
                self.flag_Decimal = False; self.vdebt += 2
                return
            case 0xD0: # Branch Not Equal
                if not self.flag_Zero:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if temppg % 256 != self.pgmctr % 256:
                        self.vdebt += 1 # Branch takes extra cycle if crossing page boundary
                    self.vdebt += 1 # Takes 1 additional cycles if nonzero
                self.vdebt += 2 # Takes 2 cycles no matter what
            case 0xEA: # NOP
                self.vdebt += 2; return
            case 0xF0: # Branch on Equal
                if self.flag_Zero:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if temppg % 256 != self.pgmctr % 256:
                        self.vdebt += 1  # Branch takes extra cycle if crossing page boundary
                    self.vdebt += 1  # Takes 1 additional cycles if nonzero
                self.vdebt += 2  # Takes 2 cycles no matter what
            case 0xD8: # Set Decimal Flag
                self.flag_Decimal = True; self.vdebt = 2
                return






        # The below line automatically increments the counter for all cases
        # This can be skipped for one byte instructions by returning, it saves space
        self.pgmctr += 1




# TODO: Function to shorten length of branch instructions?



