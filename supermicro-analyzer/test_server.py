import unittest
from unittest.mock import patch

from server import _attach_firmware, _parse_motherboard, _parse_system


class ProductParserTests(unittest.TestCase):
    def test_parses_motherboard_fields(self) -> None:
        text = """
Title: H14DSH | Motherboards | Products

# H14DSH **( For A+ Server Only )**

[![Image 9: H14DSH](https://example.test/image.png)](https://example.test/image.png)

H14 DP Hyper Server Board

### Key Features

Product SKUs **MBD-H14DSH** Physical Stats Form Factor* Proprietary
Processor CPU* Dual Socket SP5 * AMD EPYC 9005/9004 Series Processors
Core Count* Up to 384C/768T
System Memory Memory* Slot Count: 24 DIMM Slots
* Max Memory (1DPC): Up to 6TB 6400MT/s ECC DDR5 RDIMM
Memory Voltage* 1.1V
IPMI* ASPEED AST2600 BMC
Other Features* RoT
"""
        product = _parse_motherboard(
            "H14DSH",
            "https://www.supermicro.com/en/products/motherboard/H14DSH",
            text,
        )

        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(product.category, "主機板")
        self.assertEqual(product.name, "H14 DP Hyper Server Board")
        self.assertIn("AMD EPYC 9005/9004", product.cpu)
        self.assertTrue(any("24 DIMM" in item for item in product.memory))
        self.assertTrue(product.bmc)
        self.assertTrue(product.rot)

    def test_parses_system_fields(self) -> None:
        text = """
Title: SYS-511R-M | 1U | SuperServer
Markdown Content:
# UP SuperServer SYS-511R-M
Processor Single V0 Intel Xeon E-2400 processors Up to 12C/24T
System Memory Slot Count: 4 DIMM slots Max Memory: Up to 128GB DDR5
Drive Bays Configuration Default: Total 4 bays
Input / Output LAN: 1 Dedicated BMC LAN port
"""
        product = _parse_system(
            "SYS-511R-M",
            "https://www.supermicro.com/en/products/system/datasheet/sys-511r-m",
            text,
        )

        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(product.category, "系統")
        self.assertIn("Xeon E-2400", product.cpu)
        self.assertTrue(any("128GB DDR5" in item for item in product.memory))
        self.assertTrue(product.bmc)
        self.assertFalse(product.rot)

    @patch("server._fetch_official_page")
    def test_attaches_latest_firmware_versions(self, fetch_page) -> None:
        product_text = """
Title: SYS-511R-M
# UP SuperServer SYS-511R-M
Processor Intel Xeon processors
System Memory Slot Count: 4 DIMM slots
Drive Bays Configuration 4 bays
Motherboard Super X13SCH-SYS
"""
        product = _parse_system(
            "SYS-511R-M",
            "https://www.supermicro.com/en/products/system/datasheet/sys-511r-m",
            product_text,
        )
        self.assertIsNotNone(product)
        assert product is not None
        fetch_page.return_value = """
Title: Firmware Resources | Support
BIOS Revision:2.4
BMC Firmware Revision:01.05.05
"""

        updated = _attach_firmware(product, product_text, is_motherboard=False)

        self.assertEqual(updated.bios_version, "2.4")
        self.assertEqual(updated.bmc_version, "01.05.05")
        self.assertIn("MBD-X13SCH-SYS", updated.sources[-1])

    def test_rejects_not_found_page(self) -> None:
        text = """
Title: Not Found
URL Source: https://www.supermicro.com/en/products/motherboard/NOT-REAL
Markdown Content:
404
Not Found
"""
        product = _parse_motherboard(
            "NOT-REAL",
            "https://www.supermicro.com/en/products/motherboard/NOT-REAL",
            text,
        )
        self.assertIsNone(product)


if __name__ == "__main__":
    unittest.main()
