import socket
import unittest
from unittest.mock import patch

from server import (
    _attach_firmware,
    _attach_motherboard_capabilities,
    _create_servers,
    _normalize_model,
    _parse_motherboard,
    _parse_system,
)


class ProductParserTests(unittest.TestCase):
    def test_normalizes_spaces_around_model_hyphens(self) -> None:
        self.assertEqual(
            _normalize_model(" AS -2116GT-DTNF "),
            "AS-2116GT-DTNF",
        )

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
Motherboard Super X13SCH-SYS
"""
        product = _parse_system(
            "SYS-511R-M",
            "https://www.supermicro.com/en/products/system/datasheet/sys-511r-m",
            text,
        )

        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(product.category, "系統")
        self.assertEqual(product.motherboard_model, "X13SCH-SYS")
        self.assertIn("Xeon E-2400", product.cpu)
        self.assertTrue(any("128GB DDR5" in item for item in product.memory))
        self.assertTrue(product.bmc)
        self.assertFalse(product.rot)

    def test_parses_official_model_with_spaced_hyphen(self) -> None:
        text = """
Title: AS -2116GT-DTNF | 2U | SuperServer
# GrandTwin SuperServer AS -2116GT-DTNF
Processor Single processor AMD EPYC 9005 Up to 192C
GPU Up to 2 GPUs
System Memory Slot Count: 12 DIMM slots Max Memory: Up to 3TB DDR5
Drive Bays Configuration 4 bays
Motherboard Super H14SST-GE
"""
        product = _parse_system(
            "AS-2116GT-DTNF",
            "https://www.supermicro.com/en/products/system/datasheet/as-2116gt-dtnf",
            text,
        )

        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(product.model, "AS-2116GT-DTNF")
        self.assertEqual(product.motherboard_model, "H14SST-GE")
        self.assertNotIn("GPU", product.cpu)

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

        updated = _attach_firmware(product)

        self.assertEqual(updated.bios_version, "2.4")
        self.assertEqual(updated.bmc_version, "01.05.05")
        self.assertIn("MBD-X13SCH-SYS", updated.sources[-1])

    @patch("server._fetch_official_page")
    def test_system_uses_motherboard_rot_capability(self, fetch_page) -> None:
        system_text = """
# UP SuperServer SYS-TEST
Processor Single Socket processor
System Memory Slot Count: 4 DIMM slots
Drive Bays Configuration 4 bays
Motherboard Super TEST-BOARD
"""
        product = _parse_system(
            "SYS-TEST",
            "https://www.supermicro.com/en/products/system/datasheet/sys-test",
            system_text,
        )
        self.assertIsNotNone(product)
        assert product is not None
        fetch_page.return_value = """
# TEST-BOARD **( For SuperServer Only )**
[![Image](https://example.test/image.png)](https://example.test/image.png)
Test DP Server Board
### Key Features
Product SKUs **MBD-TEST-BOARD**
Processor CPU* Dual Socket E2 * Test processors
Core Count* Up to 128C
System Memory Memory* Slot Count: 16 DIMM Slots
Memory Voltage* 1.1V
IPMI* ASPEED BMC
Other Features* RoT
"""

        updated = _attach_motherboard_capabilities(product)

        self.assertTrue(updated.bmc)
        self.assertTrue(updated.rot)
        self.assertIn("/motherboard/TEST-BOARD", updated.sources[-1])

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


class ServerStartupTests(unittest.TestCase):
    def test_default_host_listens_on_ipv4_and_ipv6_loopback(self) -> None:
        servers = _create_servers("127.0.0.1", 0)
        try:
            families = {server.socket.family for server in servers}
            self.assertIn(socket.AF_INET, families)
            if socket.has_ipv6:
                self.assertIn(socket.AF_INET6, families)
        finally:
            for server in servers:
                server.server_close()


if __name__ == "__main__":
    unittest.main()
