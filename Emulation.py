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
        self.cycles = 0
        self.halt = False
        # Treating the flags as components of a byte might increase performance when it comes to pushing and pulling flags
        # I also think it would tank performance in a lot of other places where a simple boolean check is replaced with modulus math
        # There might be some good compromise, but I don't think there are major gains to be had here?
        self.flag_Carry = False
        self.flag_Zero = False
        self.flag_InterruptDisable = False
        self.flag_Decimal = False
        self.flag_Overflow = False
        self.flag_Negative = False
        self.stackptr = 0xFD

        # initialize ram ( I believe this will need to be randomized on startup in the future)
        self.addSpace = [0xff] * 0x8000
        # Initialize rom
        with open(self.rompath, "rb") as data:
            self.header = (chunk for chunk in data.read(0x10))
            self.addSpace += (chunk for chunk in data.read())
        # Move the Program Counter to correct space (Little Endian), or custom address if debug is active
        if debug:
            self.pgmctr = 0x8000
        else:
            self.pgmctr = self.addSpace[0xFFFC] + self.addSpace[0xFFFD] * 256

    def run_emu(self): # Primary event loop
        self.flag_InterruptDisable = True
        while not self.halt:
            self.opcode = self.addSpace[self.pgmctr]
            self.pgmctr += 0x1
            if self.debug:
                print("op:" + hex(self.opcode),  "pgmctr:" + hex(self.pgmctr),
                      "regA:" + hex(self.regA), "0x0:" + hex(self.addSpace[0x0]))
            self.op()

    def push(self, value): # Push value to stack, decrease stack pointer
        self.write(0x100 + self.stackptr, value)
        self.stackptr -= 1

    def pull(self): # Pull value from stack, increase stack pointer
        if self.stackptr == 0xFF:
            self.stackptr = 0x00
        else:
            self.stackptr += 1
        return self.read(0x100 + self.stackptr)

    def read(self, address=-1, mirror=True): # Read from address, if no address is specified, the address will be taken from the program coutner
        if address == -1:
            address = self.pgmctr
        while 0x1FFF > address >= 0x800 and mirror:
            address -= 0x800
        return self.addSpace[address]

    def write(self, address, data): # Write data to address in memory, no default here
        if address > 0x800:
            raise MemoryError(f"Attempted to write to invalid memory address {address} at line {self.pgmctr}")
        else:
            self.addSpace[address] = data

    def setflags(self, value, negative=True, zero=True): # Set relevant flags based on passed value.
        # I would like to make this function more comprehensive with the option to opt in and out of certain flags but I'm not sure if that's necessary
        self.flag_Negative = value > 127 and negative
        self.flag_Zero = value == 0 and zero

    def get_abs(self): # Get Absolute Address
        tlow = self.read()
        self.pgmctr += 1
        return tlow + self.read() * 256

    def get_ind(self): # Get Indirect Address
        vec = self.get_abs()
        tlow = self.read(vec)
        vec += 1
        if vec % 255 == 0:
            vec -= 255
        return tlow + self.read(vec) * 256

    def adc(self, a, b): # Add with carry
        tempval = a + b + self.flag_Carry
        self.flag_Carry = tempval > 255
        self.regA = tempval
        tempsigned = signed8(a) + signed8(b) + self.flag_Carry
        self.flag_Overflow = -128 > tempsigned > 127
        return tempval

    def asl(self, val): # Arithmetic shift left
        self.flag_Carry = val > 127
        val = (val % 128)*2
        self.setflags(val)
        return val

    def rol(self, val): # Roll Left
        willcarry = val > 127
        val = (val % 128)*2 + self.flag_Carry
        self.setflags(val)
        self.flag_Carry = willcarry
        return val

    def op(self):
        # At the beginning of each op, the program counter will point to the address immediately following the opcode
        # For operations with a length of one, a return should be used to skip this automatic increment at the end of the op function
        # These automatic increments are done in an attempt to shorten the  amount of space each op takes up, I realize this may not be best practice
        # And if it proves to be too confusing I can revisit this later
        match self.opcode:
            case 0x02:  # HTL
                self.halt = True
            case 0x06: # Bitshift Left Zero Page
                self.write(self.read(), self.asl(self.read(self.read())))
                self.cycles = 5
            case 0x08: # Push Flags
                flagbyte = 48
                if self.flag_Carry:
                    flagbyte += 1
                if self.flag_Zero:
                    flagbyte += 2
                if self.flag_InterruptDisable:
                    flagbyte += 4
                #if self.flag_Decimal:   Not necessary due to NES disabling of BCD
                #    flagbyte += 8
                if self.flag_Overflow:
                    flagbyte += 64
                if self.flag_Negative:
                    flagbyte += 128
                self.push(flagbyte); self.cycles += 3; return
            case 0x16: # Bitshift Left Zero Page, X indexed
                addr = (self.read() + self.regX) % 256
                self.write(addr, asl(self.read(addr))); self.cycles += 6
            case 0x0A: # Bitshift Left A
                self.regA = self.asl(self.regA)
                self.cycles = 2; return
            case 0x0E: # Bitshift Left Absolute
                addr = self.get_abs()
                self.write(addr, asl(self.read(addr))); self.cycles += 6
            case 0x10: # Branch on Plus
                if not self.flag_Negative:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
            # TODO: Refactor Branches, this code can be much cleaner
            case 0x18: # Clear Carry
                self.flag_Carry = False; self.cycles += 2
                return
            case 0x1E: # Bitshift Left Absolute X indexed
                addr = self.get_abs() + self.regX
                self.write(addr, self.asl(self.read(addr))); self.cycles += 7
            case 0x20: # Jump to Subroutine
                tlow = self.read(); self.pgmctr += 1
                thigh = self.read()
                self.push(math.floor(self.pgmctr/256)); self.push(self.pgmctr % 256)
                self.pgmctr = (tlow+thigh*256); self.cycles += 6
                return # prevent auto increment to pgmctr since we just set it
            case 0x28: # Pull Flags
                # TODO: Probably more efficient to do this as subtraction in a while loop?
                flags = bin(self.pull()[1:])
                while len(flags) < 8:
                    flags = "0" + flags
                self.flag_Carry = flags[7]
                self.flag_Zero = flags[6]
                self.flag_InterruptDisable = flags[5]
                # self.flag_Decimal = flags[4] Not necessary due to NES disabling BCD
                self.flag_Overflow = flags[1]
                self.flag_Negative = flags[0]
                self.cycles += 3; return
            case 0x30:  # Branch on Minus.
                if self.flag_Negative:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
            case 0x38: # Set Carry
                self.flag_Carry = True; self.cycles += 2
                return
            case 0x48: # Push Accumulator
                self.push(self.regA); self.cycles += 3
                return
            case 0x4C: # JMP
                tlow = self.read(); self.pgmctr += 1
                thigh = self.read()
                self.pgmctr = (tlow + thigh * 256); self.cycles += 3
                return # prevent auto increment to pgmctr since we just set it
            case 0x50:  # Branch on not Overflow
                if not self.flag_Overflow:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
            case 0x58: # Clear Interrupt-Disable
                self.flag_InterruptDisable = False; self.cycles += 2
                return
            case 0x60: # Return from Subroutine
                tlow = self.pull(); self.pgmctr = (tlow+self.pull()*256); self.cycles += 6
            case 0x65: # Add to Accumulator zero page
                self.regA = self.adc(self.regA, self.read())
                self.setflags(self.regA); self.cycles += 3
            case 0x68: # Pull Accumulator
                self.regA = self.pull(); self.cycles += 4
                self.setflags(self.regA)
                return
            case 0x69: # Add to accumulator immediate
                self.regA = self.adc(self.regA, self.read())
                self.setflags(self.regA); self.cycles += 2
                # Fun fact, the NES does not use the Decimal flag, ask me how much time I spent implementing BCD from the raw 6502 docs before coming to this realization
            case 0x6C: # Jump to Indirect Address
                self.pgmctr = self.get_ind(); self.cycles += 5
            case 0x6D: # Add to accumulator absolute
                addr = self.get_abs()
                self.regA = adc(self.regA, self.read(addr))
                self.setflags(self.regA); self.cycles += 4
            case 0x70:  # Branch on Overflow
                if self.flag_Overflow:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
            case 0x75: # Add to accumulator zero page, x indexed
                addr = (self.read() + self.regX) % 256
                self.regA = self.adc(self.regA, self.read(addr))
                self.setflags(self.regA); self.cycles += 4
            case 0x78: # Set Interrupt-Disable
                self.flag_InterruptDisable = True; self.cycles += 2
                return
            case 0x79:  # Add to accumulator, absolute y indexed
                addr = self.get_abs()
                self.cycles += addr % 256 + self.regY > 255  # Add cycle if page boundary crossed
                self.regA = adc(self.regA, self.read(addr + self.regY))
                self.setflags(self.regA); self.cycles += 4
            case 0x7D: # Add to accumulator, absolute x indexed
                addr = self.get_abs()
                self.cycles += addr % 256 + self.regX > 255  # Add cycle if page boundary crossed
                self.regA = adc(self.regA, self.read(addr + self.regX))
                self.setflags(self.regA); self.cycles += 4
            case 0x84: # STY Zero Page
                self.write(self.read(), self.regY); self.cycles += 3
            case 0x85: # STA Zero Page
                self.write(self.read(), self.regA); self.cycles += 3
            case 0x86: # STX Zero Page
                self.write(self.read(), self.regX); self.cycles += 3
            case 0x88: # DEY
                self.regY -= 1; self.cycles += 2; return
            case 0x8A: # TXA
                self.regA = self.regX; self.cycles += 2; return
            case 0x8C: # STY Absolute
                self.write(self.read(self.get_abs()), self.regY); self.cycles += 4
            case 0x8D: # STA absolute
                self.write(self.read(self.get_abs()), self.regA); self.cycles += 4
            case 0x8E: # STX Absolute
                self.write(self.read(self.get_abs()), self.regX); self.cycles += 4
            case 0x90: # Branch on not Carry
                if not self.flag_Carry:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
            case 0x98: # TYA
                self.regA = self.regY; self.cycles +=2; return
            case 0xAA: # TAX
                self.regX = self.regA; self.cycles += 2; return
            case 0xA0:  # immediate Y
                self.regY = self.read(); self.cycles += 2
                self.setflags(self.regY)
            case 0xA2:  # immediate X
                self.regX = self.read(); self.cycles += 2
                self.setflags(self.regX)
            case 0xA5: # LDA Zero Page
                self.regA = self.read(); self.cycles += 2
                self.setflags(self.regA)
            case 0xA8: # TAY
                self.regY = self.regA; self.cycles += 2; return
            case 0xA9:  # immediate A
                self.regA = self.read(); self.cycles += 2
                self.setflags(self.regA)
            case 0xAD: # LDA Absolute
                add = self.get_abs()
                if math.floor(add / 256) != math.floor(self.pgmctr / 256):
                    self.cycles += 1
                self.regA = self.read(self.get_abs())
                self.setflags(self.regA); self.cycles += 3
            case 0xBA: # TSX
                self.regX = self.pop()
                self.setflags(self.regX)
            case 0xB8: # Clear Overflow
                self.flag_Overflow = False; self.cycles += 2
                return
            case 0xCA: # DEX
                self.regX -= 1; self.cycles += 2; return
            case 0xC8: # INY
                self.regY += 1; self.cycles += 2; return
            case 0xD8: # Clear Decimal Flag
                self.flag_Decimal = False; self.cycles += 2
                return
            case 0xD0: # Branch Not Equal
                if not self.flag_Zero:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1 # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1 # Takes 1 additional cycles if nonzero
                self.cycles += 2 # Takes 2 cycles no matter what
            case 0xEA: # NOP
                self.cycles += 2; return
            case 0xE8: # INX
                self.regX += 1; self.cycles += 2; return
            case 0xF0: # Branch on Equal
                if self.flag_Zero:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
            case 0xF8: # Set Decimal Flag
                self.flag_Decimal = True; self.cycles = 2
                return
        # The below line automatically increments the counter for all cases
        # This can be skipped for one byte instructions by returning, it saves space
        self.pgmctr += 1


# TODO: Function to shorten length of branch instructions?



