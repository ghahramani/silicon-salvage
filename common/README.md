# Common Utilities & Bench Tools

This directory contains shared tools and scripts used across multiple router models:

- **`tftp_server.py`**: Lightweight, standalone Python TFTP server for staging initramfs images during recovery and initial RAM boots.
  ```bash
  sudo python3 tftp_server.py --dir /path/to/firmware/
  ```

### Serial UART Requirements
All routers in this project operate at **3.3V TTL** logic levels. Connecting 5V serial adapters can permanently damage the SoC.

We recommend the **[Waveshare Industrial USB-to-TTL Serial Converter](https://www.amazon.co.uk/dp/B0CX55K4RG?&linkCode=ll2&tag=navid015-21&linkId=fb0958a59eb9c1688fec1959cdadcac8&ref_=as_li_ss_tl)** for hardware galvanic isolation and TVS surge suppression during all serial flashing.
