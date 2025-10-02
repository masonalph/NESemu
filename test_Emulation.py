from Emulation import Emulation
import unittest
import math


class NESemuTest(unittest.TestCase):
    def test_op69(self):
        self.scene = Emulation("test.nes")
        for a in range(0, 255):
            for b in range(0, 255):
                for c in [True, False]:
                    # Set test scene
                    teststr = f"a{a} b{b} c{c}"
                    self.scene.halt = False
                    self.scene.pgmctr = 0x8000
                    self.scene.addSpace[0x8000:0x8004] = [0xa9, a, 0x69, b, 0x02]
                    self.scene.flag_Carry = c
                    self.scene.run_emu()
                    # Check assertions
                    tsum = a + b + c
                    if tsum == 0:
                        assert self.scene.flag_Zero, f"Failure testing $69, high expected Z" + teststr
                    else:
                        assert not self.scene.flag_Zero, f"Failure testing $69, low expected Z" + teststr
                    if tsum > 255:
                        assert self.scene.flag_Carry, f"Failure testing $69, high expected C" + teststr
                        tsum -= 255
                    else:
                        assert not self.scene.flag_Carry, f"Failure testing $69, low expected C" + teststr
                    if tsum > 127:
                        assert self.scene.flag_Negative,  f"Failure testing $69, high expected N" + teststr
                    else:
                        assert not self.scene.flag_Negative, f"Failure testing $69, low expected N" + teststr
                    assert self.scene.regA == tsum, f"Failure at $69 {a} + {b} + {c}= {tsum}, got {self.scene.regA}"


unittest.main()

