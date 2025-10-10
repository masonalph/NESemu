from customTypes import *
import math
import csv
from pathlib import Path

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
        self.logger = []
        self.iter = 0

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

    def run_emu(self, log): # Primary event loop
        logger = csv.writer(log)
        logger.writerow(["Program Counter", "Op", "Reg A", "Reg X", "Reg Y", "Fstring"])
        self.flag_InterruptDisable = True
        while not self.halt:
            self.opcode = self.addSpace[self.pgmctr]
            logger.writerow([self.pgmctr, self.opcode, self.regA, self.regX, self.regY, self.build_Fstring()])
            self.pgmctr += 0x1
            self.op()

    def build_Fstring(self):
        base = ""
        if self.flag_Negative:
            base = base + "N"
        else:
            base = base + "n"
        if self.flag_Overflow:
            base = base + "V"
        else:
            base = base + "v"
        base = base + "TB"
        if self.flag_Decimal:
            base = base + "D"
        else:
            base = base + "d"
        if self.flag_Zero:
            base = base + "Z"
        else:
            base = base + "z"
        if self.flag_Carry:
            base = base + "C"
        else:
            base = base + "c"
        return base

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

    def set_flags(self, value, negative=True, zero=True): # Set relevant flags based on passed value.
        # I would like to make this function more comprehensive with the option to opt in and out of certain flags but I'm not sure if that's necessary
        self.flag_Negative = value > 127 and negative
        self.flag_Zero = value == 0 and zero

    def get_abs(self): # Get Absolute Address
        tlow = self.read()
        self.pgmctr += 1
        return tlow + self.read() * 256
    
    def get_abs_indx(self, addr, index):
        self.cycles += addr % 256 + index > 255
        return addr + index
    # TODO, utilize this function in indirect inclusive / exclusive?

    def get_incl_indr(self, offset=-1):
        if offset == -1:
            offset = self.regX
        tlow = self.read(self.pgmctr + offset)
        thigh = self.read(self.pgmctr + offset + 1)
        return tlow + thigh*256

    def get_excl_indr(self, offset=-1):
        if offset == -1:
            offset = self.regY
        # Why return 2 different values? $91 does NOT cost an additional cycle for crossing page boundaries unlike every other Exclusive Indirect Addressing,
        # so we will let the op choose whether it ones to add that extra cycle in or not
        tlow = self.read(self.read())
        thigh = self.read(self.read() + 1)
        return (tlow + thigh*256) + offset, tlow % 255 == 0

    def adc(self, a, b): # Add with carry
        tempval = a + b + self.flag_Carry
        self.flag_Carry = tempval > 255
        self.regA = tempval
        tempsigned = signed8(a) + signed8(b) + self.flag_Carry
        self.flag_Overflow = -128 > tempsigned > 127
        self.set_flags(tempval)
        return tempval

    def sbc(self, a, b): # Subtract with Carry
        tempval = a - b - (not self.flag_Carry)
        self.flag_Carry = tempval > 0
        while tempval < 0:
            tempval += 256
        self.set_flags(tempval)
        t1 = a > 127
        t2 = b > 127
        t3 = tempval > 127
        # Get the signed flag of each number, set overflow if
        # A positive - negative = negative or if a negative - positive = positive
        # Simplified as sign of a != sign of b and sign of b == sign of c
        self.flag_Overflow = t1 != t2 and t2 == t3
        return tempval
        # overflow if bit 7 0,1,1 or 1,0,0

    def asl(self, val): # Arithmetic shift left
        self.flag_Carry = val > 127
        val = (val % 128)*2
        self.set_flags(val)
        return val

    def lsr(self, val): # Logical Shift Right
        self.flag_Carry = val % 2 == 1
        val -= self.flag_Carry
        val /= 2
        self.set_flags(val)
        return val

    def rol(self, val): # Roll Left
        willcarry = val > 127
        val = (val % 128)*2 + self.flag_Carry
        self.set_flags(val)
        self.flag_Carry = willcarry
        return val

    def ror(self, val): # Roll Right
        willcarry = val % 2 == 1
        val -= willcarry
        val /= 2
        val += (self.flag_Carry*128)
        self.set_flags(val)
        self.flag_Carry = willcarry
        return val
        # There may be a more efficient way to set the 8th bit then mult by 0 / 1

    def inc(self, val):
        val += 1
        if val == 256:
            val = 0
        self.set_flags(val)
        return val

    def cmp(self, a, b):
        self.flag_Zero = a == b
        self.flag_Negative = (a - b) > 127
        self.flag_Carry = a >= b

    def bit(self, input):
        self.flag_Zero = (input & self.regA) == 0
        self.flag_Negative = input > 127
        self.flag_Overflow = input > 63

    def op(self):
        # I'M GONNA RENAME INDIRECT INDEXED ADDRESSING TO EXCLUSIVE ADDRESSING AND INDEXED INDIRECT ADDRESSING TO INCLUSIVE ADDRESSING
        # Okay so ($04, X) will be called Inclusive indirect and ($04), Y will be called Exclusive please email all of your complaints to gaben@valvesoftware.com

        # At the beginning of each op, the program counter will point to the address immediately following the opcode
        # For operations with a length of one, a return should be used to skip this automatic increment at the end of the op function
        # These automatic increments are done in an attempt to shorten the  amount of space each op takes up, I realize this may not be best practice
        # And if it proves to be too confusing I can revisit this later
        match self.opcode:
            case 0x00:
                # <editor-fold desc="Break">
                self.pgmctr += 1
                self.push(math.floor(self.pgmctr / 256)); self.push(self.pgmctr % 256)
                flags = self.flag_Carry
                flags += self.flag_Zero * 2
                flags += self.flag_InterruptDisable * 4
                flags += self.flag_Decimal * 8
                flags += 0x30
                flags += self.flag_Overflow * 64
                flags += self.flag_Negative * 128
                self.push(flags)
                tlow = self.read(0xFFFE)
                thigh = self.read(0xFFFF)
                self.pgmctr = tlow + thigh * 256
                self.cycles += 7
                return
                # </editor-fold>
            case 0x01:
                # <editor-fold desc="OR w/ Accumulator, Indirect X (Inclusive Indirect)">
                addr = self.get_incl_indr()
                self.regA |= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 6
                # </editor-fold>
            case 0x02:
                # <editor-fold desc="Halt">
                self.halt = True
                # </editor-fold>
            case 0x05:
                # <editor-fold desc="OR w/ Accumulator Zero Page">
                addr = self.read()
                self.regA |= self.read(addr)
                self.set_flags(self.regA); self.cycles += 3
                # </editor-fold>
            case 0x06:
                # <editor-fold desc="Arithmetic Shift Left Zero Page">
                addr = self.read()
                self.write(addr, self.asl(self.read(addr)))
                self.cycles = 5
                # </editor-fold>
            case 0x08:
                # <editor-fold desc="Push Flags">
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
                # </editor-fold>
            case 0x09:
                # <editor-fold desc="OR w/ Accumulator Immediate">
                self.regA |= self.read()
                self.set_flags(self.regA); self.cycles += 2
                # </editor-fold>
            case 0x0D:
                # <editor-fold desc="OR w/ Accumulator Absolute">
                self.regA |= self.read(self.get_abs())
                self.set_flags(self.regA); self.cycles += 4
                # </editor-fold>
            case 0x0A:
                # <editor-fold desc="Arithmetic Shift Left Accumulator">
                self.regA = self.asl(self.regA)
                self.cycles = 2; return
                # </editor-fold>
            case 0x0E:
                # <editor-fold desc="Arithmetic Shift Left Absolute">
                addr = self.get_abs()
                self.write(addr, asl(self.read(addr))); self.cycles += 6
                # </editor-fold>
            case 0x10:
                # <editor-fold desc="Branch on Plus">
                if not self.flag_Negative:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                # </editor-fold>
            # TODO: Refactor Branching to use get_abs_indx()
            case 0x11:
                # <editor-fold desc="OR w/ Accumulator Indirect, Y Indexed (Exclusive Indirect)">
                addr, addcycle = self.get_excl_indr()
                self.regA |= self.read(addr)
                self.cycles += addcycle + 5
                self.set_flags(self.regA)
                # </editor-fold>
            case 0x15:
                # <editor-fold desc="OR w/ Accumulator Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.regA |= self.read(addr)
                self.set_flags(self.regA); self.cycles += 4
                # </editor-fold>
            case 0x16:
                # <editor-fold desc="Arithmetic Shift Left Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.write(addr, asl(self.read(addr))); self.cycles += 6
                # </editor-fold>
            case 0x18:
                # <editor-fold desc="Clear Carry">
                self.flag_Carry = False; self.cycles += 2
                return
                # </editor-fold>
            case 0x19:
                # <editor-fold desc="OR w/ Accumulator Absolute, Y Index">
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.regA |= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x1D:
                # <editor-fold desc="OR w/ Accumulator Absolute, X Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.regA |= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x1E:
                # <editor-fold desc="Arithmetic Shift Left Absolute, X Indexed">
                addr = self.get_abs() + self.regX
                self.write(addr, self.asl(self.read(addr))); self.cycles += 7
                # </editor-fold>
            case 0x20:
                # <editor-fold desc="Jump to Subroutine">
                tlow = self.read(); self.pgmctr += 1
                thigh = self.read()
                self.push(math.floor(self.pgmctr/256)); self.push(self.pgmctr % 256)
                self.pgmctr = (tlow+thigh*256); self.cycles += 6
                return # prevent auto increment to pgmctr since we just set it
                # </editor-fold>
            case 0x21:
                # <editor-fold desc="AND w/ Accumulator Indirect, X Indexed (Inclusive Indirect)">
                addr = self.get_incl_indr()
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 6
                # </editor-fold>
            case 0x24:
                # <editor-fold desc="test Bit Zero Page">
                addr = self.read()
                self.bit(self.read(addr))
                self.cycles += 3
                # </editor-fold>
            case 0x25:
                # <editor-fold desc="AND w/ Accumulator Zero Page">
                addr = self.read()
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 3
                # </editor-fold>
            case 0x26:
                # <editor-fold desc="Rotate Left Zero Page">
                addr = self.read()
                self.write(addr, rol(self.read(addr))); self.cycles += 5
                # </editor-fold>
            case 0x28:
                # <editor-fold desc="Pull Flags">
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
                # </editor-fold>
                # TODO: Probably more efficient to do this as subtraction in a while loop?
            case 0x29:
                # <editor-fold desc="AND w/ Accumulator Immediate">
                self.regA &= self.read()
                self.set_flags(self.regA)
                self.cycles += 2
                # </editor-fold>
            case 0x2A:
                # <editor-fold desc="Rotate Left Accumulator">
                self.regA = self.rol(self.regA)
                self.cycles += 2; return
                # </editor-fold>
            case 0x2C:
                # <editor-fold desc="test Bit Absolute">
                addr = self.get_abs()
                self.bit(self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0x2D:
                # <editor-fold desc="AND w/ Accumulator Absolute">
                addr = self.get_abs()
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x2E:
                # <editor-fold desc="Rotate Left Absolute">
                addr = self.get_abs()
                self.write(addr, rol(self.read(addr)))
                self.cycles += 6
                # </editor-fold>
            case 0x30:
                # <editor-fold desc="Branch on Minus">
                if self.flag_Negative:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                # </editor-fold>
            case 0x31:
                # <editor-fold desc="AND w/ Accumulator Indirect, Y Indexed (Exclusive Indirect)">
                addr, addcycle = self.get_excl_indr()
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 5 + addcycle
                # </editor-fold>
            case 0x35:
                # <editor-fold desc="AND w/ Accumulator Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x36:
                # <editor-fold desc="Rotate Left Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.write(addr, rol(self.read(addr))); self.cycles += 6
                # </editor-fold>
            case 0x38:
                # <editor-fold desc="Set Carry">
                self.flag_Carry = True; self.cycles += 2
                return
                # </editor-fold>
            case 0x39:
                # <editor-fold desc="AND w/ Accumulator Absolute Y Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x3D:
                # <editor-fold desc="AND w/ Accumulator Absolute X Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x3E:
                # <editor-fold desc="Rotate Left Absolute, X Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regX) # Add cycle if page boundary crossed
                self.write(addr, rol(self.read(iaddr)))
                self.cycles += 7
                # </editor-fold>
            case 0x40:
                # <editor-fold desc="Return from Interrupt">
                flags = self.pull()
                tlow = self.pull; thigh = self.pull()
                self.pgmctr = tlow + thigh * 256
                self.flag_Negative = flags > 127
                flags -= self.flag_Negative * 128
                self.flag_Overflow = flags > 63
                flags -= self.flag_Overflow * 64 - 0x30
                self.flag_Decimal = flags > 7
                flags -= self.flag_Decimal * 8
                self.flag_InterruptDisable = flags > 3
                flags -= self.flag_InterruptDisable
                self.flag_Zero = flags > 1
                self.flag_Carry = flag % 2 == 1
                self.cycles += 7
                return
                # </editor-fold>
            case 0x41:
                # <editor-fold desc="EOR w/ Accumulator Indirect, X Indexed (Inclusive Indirect)">
                addr = self.get_incl_indr()
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 6
                # </editor-fold>
            case 0x45:
                # <editor-fold desc="EOR w/ Accumulator Zero Page">
                addr = self.read()
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 3
                # </editor-fold>
            case 0x46:
                # <editor-fold desc="Logical Shift Right Zero Page">
                addr = self.read()
                self.write(addr, lsr(self.read(addr)))
                self.cycles += 5
                # </editor-fold>
            case 0x48:
                # <editor-fold desc="Push Accumulator">
                self.push(self.regA); self.cycles += 3
                return
                # </editor-fold>
            case 0x49:
                # <editor-fold desc="EOR w/ Accumulator Immediate">
                self.regA ^= self.read()
                self.set_flags(self.regA)
                self.cycles += 2
                # </editor-fold>
            case 0x4A:
                # <editor-fold desc="Logical Shift Right Accumulator">
                self.regA = self.lsr(self.regA)
                self.cycles += 2; return
                # </editor-fold>
            case 0x4C:
                # <editor-fold desc="Jump">
                tlow = self.read(); self.pgmctr += 1
                thigh = self.read()
                self.pgmctr = (tlow + thigh * 256); self.cycles += 3
                return # prevent auto increment to pgmctr since we just set it
                # </editor-fold>
            case 0x4D:
                # <editor-fold desc="EOR w/ Accumulator Absolute">
                addr = self.get_abs()
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x4E:
                # <editor-fold desc="Logical Shift Right Absolute">
                addr = self.get_abs()
                self.write(addr, rol(self.read(addr)))
                self.cycles += 6
                # </editor-fold>
            case 0x50:
                # <editor-fold desc="Branch on Not Overflow">
                if not self.flag_Overflow:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                # </editor-fold>
            case 0x51:
                # <editor-fold desc="EOR w/ Accumulator Indirect, Y Indexed (Exclusive Indirect)">
                addr, addcycle = self.get_excl_indr()
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 5 + addcycle
                # </editor-fold>
            case 0x55:
                # <editor-fold desc="EOR w/ Accumulator Zero Page, X Indexed">
                addr = self.read() + x
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x56:
                # <editor-fold desc="Logical Shift Right Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.write(addr, lsr(self.read(addr)))
                # </editor-fold>
            case 0x58:
                # <editor-fold desc="Clear Interrupt-Disable">
                self.flag_InterruptDisable = False; self.cycles += 2
                return
                # </editor-fold>
            case 0x59:
                # <editor-fold desc="EOR w/ Accumulator Absolute Y Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regY)  # Add cycle if page boundary crossed
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x5D:
                # <editor-fold desc="EOR w/ Accumulator Absolute X Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regX)  # Add cycle if page boundary crossed
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                # </editor-fold>
            case 0x5E:
                # <editor-fold desc="Logical Shift Right Absolute, X Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regX)  # Add cycle if page boundary crossed
                self.write(addr, lsr(self.read(addr))); self.cycles += 7
                # </editor-fold>
            case 0x60:
                # <editor-fold desc="Return from Subroutine">
                tlow = self.pull()
                self.pgmctr = (tlow+self.pull()*256); self.cycles += 6
                # </editor-fold>
            case 0x61:
                # <editor-fold desc="Add with Carry Indirect, X Indexed (Inclusive Indirect)">
                addr = self.get_incl_indr()
                self.regA = self.adc(self.read(addr), self.regA)
                self.cycles += 6
                # </editor-fold>
            case 0x65:
                # <editor-fold desc="Add to Accumulator Zero Page">
                addr = self.read()
                self.regA = self.adc(self.regA, self.read(addr))
                self.cycles += 3
                # </editor-fold>
            case 0x66:
                # <editor-fold desc="Rotate Right Zero Page">
                addr = self.read()
                self.write(addr, ror(self.read(addr))); self.cycles += 5
                # </editor-fold>
            case 0x68:
                # <editor-fold desc="Pull Accumulator">
                self.regA = self.pull(); self.cycles += 4
                self.set_flags(self.regA)
                return
                # </editor-fold>
            case 0x69:
                # <editor-fold desc="Add to Accumulator Immediate">
                self.regA = self.adc(self.regA, self.read())
                self.cycles += 2
                # Fun fact, the NES does not use the Decimal flag, ask me how much time I spent implementing BCD from the raw 6502 docs before coming to this realization
                # </editor-fold>
            case 0x6A:
                # <editor-fold desc="Rotate Right Accumulator">
                self.regA = self.ror(self.regA)
                self.cycles += 2; return
                # </editor-fold>
            case 0x6C:
                # <editor-fold desc="Jump to Indirect Address">
                addr = self.get_abs()
                tlow = self.read(addr)
                addr += 1
                if addr % 256 == 0:
                    addr -= 256
                thigh = self.read(addr)
                self.pgmctr = tlow + thigh*256
                self.cycles += 5
                # </editor-fold>
            case 0x6D:
                # <editor-fold desc="Add to Accumulator Absolute">
                addr = self.get_abs()
                self.regA = adc(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0x6E:
                # <editor-fold desc="Rotate Right Absolute">
                addr = self.get_abs()
                self.write(addr,self.ror(self.read(addr)))
                self.cycles += 6
                # </editor-fold>
            case 0x70:
                # <editor-fold desc="Branch on Overflow">
                if self.flag_Overflow:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                # </editor-fold>
            case 0x71:
                # <editor-fold desc="Add with Carry Indirect, Y Indexed (Exclusive Indirect)">
                addr, addcycle = self.get_excl_indr()
                self.regA = self.adc(self.regA, self.read(addr))
                self.cycles += 5 + addcycle
                # </editor-fold>
            case 0x75:
                # <editor-fold desc="Add to Accumulator Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.regA = self.adc(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0x76:
                # <editor-fold desc="Rotate Right Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.ror(self.read(addr)))
                self.cycles += 6
                # </editor-fold>
            case 0x78:
                # <editor-fold desc="Set Interrupt-Disable">
                self.flag_InterruptDisable = True; self.cycles += 2
                return
                # </editor-fold>
            case 0x79:
                # <editor-fold desc="Add to Accumulator Absolute, Y Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regY) # Add cycle if page boundary crossed
                self.regA = adc(self.regA, self.read(addr + self.regY))
                self.cycles += 4
                # </editor-fold>
            case 0x7D:
                # <editor-fold desc="Add to Accumulator Absolute, X Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regX)  # Add cycle if page boundary crossed
                self.regA = adc(self.regA, self.read(addr + self.regX))
                self.cycles += 4
                # </editor-fold>
            case 0x7E:
                # <editor-fold desc="Rotate Right Absolute, X Indexed">
                addr = self.get_abs() + self.regX # No Additional cycles when boundary crossed
                self.write(addr, self.ror(self.read(addr)))
                self.cycles += 7
                # </editor-fold>
            case 0x84:
                # <editor-fold desc="STY Zero Page">
                self.write(self.read(), self.regY); self.cycles += 3
                # </editor-fold>
            case 0x85:
                # <editor-fold desc="STA Zero Page">
                self.write(self.read(), self.regA); self.cycles += 3
                # </editor-fold>
            case 0x86:
                # <editor-fold desc="STX Zero Page">
                self.write(self.read(), self.regX); self.cycles += 3
                # </editor-fold>
            case 0x88:
                # <editor-fold desc="Decrement Y">
                self.regY -= 1; self.cycles += 2
                self.set_flags(self.regY)
                # </editor-fold>
            case 0x8A:
                # <editor-fold desc="Transfer X > A">
                self.regA = self.regX; self.cycles += 2
                self.set_flags(self.regA); return
                # </editor-fold>
            case 0x8C:
                # <editor-fold desc="Store Register Y Absolute">
                self.write(self.read(self.get_abs()), self.regY); self.cycles += 4
                # </editor-fold>
            case 0x8D:
                # <editor-fold desc="Store Register A Absolute">
                self.write(self.read(self.get_abs()), self.regA); self.cycles += 4
                # </editor-fold>
            case 0x8E:
                # <editor-fold desc="Store Register X Absolute">
                self.write(self.read(self.get_abs()), self.regX); self.cycles += 4
                # </editor-fold>
            case 0x90:
                # <editor-fold desc="Branch on Not Carry">
                if not self.flag_Carry:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                # </editor-fold>
            case 0x98:
                # <editor-fold desc="Transfer Y > A">
                self.regA = self.regY; self.cycles += 2
                self.set_flags(self.regA); return
                # </editor-fold>
            case 0xAA:
                # <editor-fold desc="Transfer A > X">
                self.regX = self.regA; self.cycles += 2
                self.set_flags(self.regX); return
                # </editor-fold>
            case 0xA0:
                # <editor-fold desc="Load Y Immediate">
                self.regY = self.read(); self.cycles += 2
                self.set_flags(self.regY)
                # </editor-fold>
            case 0xA2:
                # <editor-fold desc="Load Immediate X">
                self.regX = self.read(); self.cycles += 2
                self.set_flags(self.regX)
                # </editor-fold>
            case 0xA5:
                # <editor-fold desc="Load A Zero Page">
                self.regA = self.read(); self.cycles += 2
                self.set_flags(self.regA)
                # </editor-fold>
            case 0xA8:
                # <editor-fold desc="Transfer A > Y">
                self.regY = self.regA; self.cycles += 2
                self.set_flags(self.regY); return
                # </editor-fold>
            case 0xA9:
                # <editor-fold desc="Load A Immediate">
                self.regA = self.read(); self.cycles += 2
                self.set_flags(self.regA)
                # </editor-fold>
            case 0xAD:
                # <editor-fold desc="Load A Absolute">
                addr = self.get_abs()
                self.regA = self.read(addr)
                self.set_flags(self.regA); self.cycles += 4
                # </editor-fold>
            case 0xBA:
                # <editor-fold desc="Transfer Stack Pointer to X">
                self.regX = self.pull()
                self.set_flags(self.regX)
                # </editor-fold>
            case 0xB8:
                # <editor-fold desc="Clear Overflow">
                self.flag_Overflow = False; self.cycles += 2
                return
                # </editor-fold>
            case 0xC1:
                # <editor-fold desc="Compare with Accumulator Indirect, X Indexed (Inclusive Indirect)">
                addr = self.get_incl_indr()
                self.cmp(self.regA, self.read(addr))
                self.cycles += 6
                # </editor-fold>
            case 0xC5:
                # <editor-fold desc="Compare with Accumulator Zero Page">
                addr = self.read()
                self.cmp(self.regA, self.read())
                self.cycles += 3
                # </editor-fold>
            case 0xC8:
                # <editor-fold desc="Increment Y">
                self.regY = self.inc(self.regY)
                self.cycles += 2; return
                # </editor-fold>
            case 0xC9:
                # <editor-fold desc="Compare with Accumulator Immediate">
                self.cmp(self.regA, self.read())
                self.cycles += 2
                # </editor-fold>
            case 0xCA:
                # <editor-fold desc="Decrement X">
                self.regX -= 1; self.cycles += 2
                self.set_flags(self.regX); return
                # </editor-fold>
            case 0xCD:
                # <editor-fold desc="Compare with Accumulator Absolute">
                addr = self.get_abs()
                self.cmp(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0xD0:
                # <editor-fold desc="Branch on Not Equal">
                if not self.flag_Zero:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1 # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1 # Takes 1 additional cycles if nonzero
                self.cycles += 2 # Takes 2 cycles no matter what
                # </editor-fold>
            case 0xD1:
                # <editor-fold desc="Compare with Accumulator Indirect, Y Indexed (Exclusive Indirect)">
                addr = self.get_incl_indr()
                self.cmp(self.regA, self.read(addr))
                self.cycles += 5
                # </editor-fold>
            case 0xD5:
                # <editor-fold desc="Compare with Accumulator Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.cmp(self.regA, self.read())
                self.cycles += 3
                # </editor-fold>
            case 0xD8:
                # <editor-fold desc="Clear Decimal -- Not Used">
                self.flag_Decimal = False; self.cycles += 2
                return
                # </editor-fold>
            case 0xD9:
                # <editor-fold desc="Compare with Accumulator Absolute, y Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.cmp(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0xDD:
                # <editor-fold desc="Compare with Accumulator Absolute, X Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.cmp(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0xE1:
                # <editor-fold desc="Subtract with Carry Indirect, X Indexed (Inclusive Indirect)">
                addr = self.get_incl_indr()
                self.regA = self.sdc(self.regA, self.read(addr))
                self.cycles += 6
                # </editor-fold>
            case 0xE5:
                # <editor-fold desc="Subtract with Carry Zero Page">
                addr = self.read()
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 3
                # </editor-fold>
            case 0xE6:
                # <editor-fold desc="Increment Memory Zero page">
                addr = self.read()
                self.write(addr, self.inc(self.read(addr)))
                self.cycles += 5
                # </editor-fold>
            case 0xE8:
                # <editor-fold desc="Increment X">
                self.regX = self.inc(self.regX)
                self.cycles += 2; return
                # </editor-fold>
            case 0xE9:
                # <editor-fold desc="Subtract with Carry Immediate">
                self.regA = self.sbc(self.regA, self.read())
                self.cycles += 2
                # </editor-fold>
            case 0xEA:
                # <editor-fold desc="No Operation">
                self.cycles += 2; return
                # </editor-fold>
            case 0xED:
                # <editor-fold desc="Subtract with Carry Absolute">
                addr = self.get_abs()
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0xEE:
                # <editor-fold desc="Increment Memory Absolute">
                addr = self.get_abs()
                self.write(addr, self.inc(self.read(addr)))
                self.cycles += 6
                # </editor-fold>
            case 0xF0:
                # <editor-fold desc="Branch on Equal">
                if self.flag_Zero:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                # </editor-fold>
            case 0xF1:
                # <editor-fold desc="Subtract with Carry Indirect, Y Indexed (Exclusive Indirect)">
                addr, addcycle = self.get_excl_indr()
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 5 + addcycle
                # </editor-fold>
            case 0xF5:
                # <editor-fold desc="Subtract with Carry Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0xF6:
                # <editor-fold desc="Increment Memory Zero Page, X Indexed">
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.inc(self.read(addr)))
                self.cycles += 6
                # </editor-fold>
            case 0xF8:
                # <editor-fold desc="Set Decimal Flag -- Not Used">
                self.flag_Decimal = True; self.cycles = 2
                return
                # </editor-fold>
            case 0xF9:
                # <editor-fold desc="Subtract with Carry Absolute, Y Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.regA = self.sdc(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0xFD:
                # <editor-fold desc="Subtract with Carry Absolute, X Indexed">
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.regA = self.sdc(self.regA, self.read(addr))
                self.cycles += 4
                # </editor-fold>
            case 0xFE:
                # <editor-fold desc="Increment Memory Absolute, X Indexed">
                addr = self.get_abs + self.regX
                self.write(addr, self.inc(self.read(addr)))
                self.cycles += 7 # No additional cycles for crossing page boundary
                # </editor-fold>
        # The below line automatically increments the counter for all cases
        # This can be skipped for one byte instructions by returning, it saves space
        self.pgmctr += 1

# TODO: Check if I can simplify ADC/SBC to not take RegA as an argument, as well as get_abs_inx taking get_abs as an arg
# TODO: Function to shorten length of branch instructions?
# TODO: Implement Overflow of 16 bit addresses, double check 8 bits are also handled correctly


