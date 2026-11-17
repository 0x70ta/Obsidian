# OBSIDIAN

**Encrypted USB mass-storage prototype**\
**Hardware:** Seeed Studio XIAO ESP32-S3 + SPI microSD card\
**Firmware line:** v2.0 prototype\
**Status:** Experimental --- not production-ready

> OBSIDIAN is a prototype that exposes one password-unlocked logical
> volume at a time over USB Mass Storage. The ESP32-S3 translates USB
> logical-sector reads and writes into encrypted blocks stored on the
> microSD card.

## Current project status

The following has been observed during the current hardware session:

-   The ESP32-S3 boots and responds to the desktop CLI with `PONG`.
-   The microSD card is detected. Reported capacity: `122142720`
    sectors.
-   Formatting the two volume headers returns `FORMAT_RESULT=SUCCESS`.
-   Decoy password verification returns `DIAG_PASSWORD_CHECK=PASS`.
-   The firmware creates the virtual MBR and returns
    `DIAG_MBR_CREATE_WRITE_OK`.
-   Unlock completes with `UNLOCK_RESULT=SUCCESS`.
-   Windows enumerates a device as **USB Drive (D:)**.
-   Opening D: currently reports that the volume does not contain a
    recognized filesystem.

**Interpretation:** USB enumeration and the firmware's initial
logical-volume setup have succeeded. A Windows-readable filesystem has
not yet been confirmed. The next planned step is to format only the
virtual OBSIDIAN drive (D:) as exFAT, after confirming in Disk
Management that D: is the OBSIDIAN virtual disk and not the physical
microSD card. Then perform a file write/eject/lock/unlock/read-back
test.

No claim is made yet that file persistence, hidden-volume isolation,
power-loss recovery, or production security has been validated.

## Features and design

-   AES-256-GCM authenticated encryption for 4 KiB logical blocks.
-   PBKDF2-HMAC-SHA256 password-based key derivation (200,000
    iterations).
-   Separate decoy and hidden volume credentials.
-   One logical volume exposed at a time.
-   USB Mass Storage callbacks translate logical sectors to encrypted
    SD-card blocks.
-   Dual-slot block updates with generation counters.
-   Serial command interface for status, format, unlock, lock, and help.
-   Physical button on D1 requests a lock on a short press.
-   Onboard LED on GPIO21 is active-low.

## Hardware

### Board and wiring

  Signal               XIAO ESP32-S3 pin
  ---------------- ---------------------
  SD SPI SCK                          D8
  SD SPI MISO                         D9
  SD SPI MOSI                        D10
  SD chip select                      D2
  SD VCC                             3V3
  SD GND                             GND
  Lock button                  D1 to GND
  Onboard LED        GPIO21 (active-low)

The button uses `INPUT_PULLUP`.

### Arduino IDE configuration

Firmware target notes:

-   Board: Seeed Studio XIAO ESP32-S3
-   Arduino-ESP32 core target: 3.3.12
-   USB Mode: **USB-OTG (TinyUSB)**
-   CDC On Boot: enabled
-   DFU / MSC On Boot: disabled; firmware registers and starts its own
    MSC interface

Use the actual COM port shown by Windows Device Manager. It may change
between connections.

## Logical and physical storage layout

### Logical volumes

  Volume     Logical size   Logical sectors (512 bytes each)
  -------- -------------- ----------------------------------
  Decoy             4 GiB                          8,388,608
  Hidden           20 GiB                         41,943,040

The USB MSC LUN is configured for the 20 GiB maximum. In decoy mode, the
virtual MBR describes a 4 GiB partition beginning at logical sector
2048. The hidden mode uses the 20 GiB logical capacity.

### Encrypted physical layout

-   Logical block size: 4,096 bytes (8 logical sectors).
-   Each block has two physical slots.
-   Each slot occupies 9 SD sectors: 8 ciphertext sectors plus 1
    metadata sector.
-   Two slots therefore occupy 18 physical SD sectors per 4 KiB logical
    block.
-   The first 2,048 physical SD sectors are reserved.
-   Decoy physical storage begins at physical sector 2,048.
-   Hidden physical storage follows the decoy physical allocation.
-   Volume headers are stored at physical SD sectors 0 (decoy) and 1
    (hidden).

This layout has storage overhead for authentication metadata and the
second slot. Do not assume that the full raw microSD capacity is
available as user-visible capacity.

### Block metadata

The metadata sector includes the slot marker `OBSV2SLOT`, volume
identifier, logical block number, generation counter, nonce, and GCM
authentication tag. The reader selects the valid slot with the highest
generation. A block whose two slots are recognized as unused is returned
as zero-filled data.

The current initialization patch treats metadata sectors without the
`OBSV2SLOT` marker as unused. This helps initialize a logical volume on
a card that previously contained unrelated data, but it has a
limitation: if both metadata markers for a previously written block are
destroyed, that state can be mistaken for an unused block. This is one
reason the prototype must not hold important data.

## Cryptography and password handling

-   Passwords are entered in the desktop CLI without echo.
-   The CLI converts the UTF-8 password bytes to hexadecimal for serial
    transport.
-   Firmware decodes the hexadecimal string and derives a 32-byte key
    with PBKDF2-HMAC-SHA256.
-   Each volume has a random salt and a password-verification record
    protected with AES-GCM.
-   The password itself is not written to the volume header.
-   Data blocks use AES-256-GCM with a 12-byte nonce and 16-byte
    authentication tag.
-   The nonce is derived from the volume key, volume identifier, logical
    block number, and generation counter.

This describes the prototype implementation; it is not an independent
cryptographic audit. In particular, nonce uniqueness, metadata
integrity, crash consistency, key lifecycle, and the complete threat
model still need review before any security claims are made.

## Firmware serial protocol

The firmware accepts newline-terminated commands at 115200 baud.

  Command                             Purpose
  ----------------------------------- --------------------------------------------------
  `PING`                              Connection check; replies `PONG`
  `STATUS`                            Prints SD, unlock, and MSC status
  `FORMAT <decoy-hex> <hidden-hex>`   Writes the two volume headers
  `UNLOCK D <password-hex>`           Unlocks the decoy volume
  `UNLOCK H <password-hex>`           Unlocks the hidden volume
  `LOCK`                              Removes USB media and clears active key material
  `HELP`                              Prints command syntax

Password input in the CLI is constrained to 8--64 UTF-8 bytes before hex
encoding.

### Important format behavior

`FORMAT` writes the volume headers to physical SD sectors 0 and 1. It
does **not** wipe the entire microSD card. However, it replaces those
two sectors and establishes new volume credentials. Do not run it again
unless intentionally reinitializing the volumes and accepting that the
existing credentials/data relationship will be changed.

## Current operating-system support

**Windows 11 is the current working and tested host operating system for
this project.** The desktop CLI is being used from Windows, and the USB
Mass Storage device has been detected by Windows as `USB Drive (D:)`.

Linux and macOS compatibility may be possible because the device uses
standard USB Mass Storage, but neither operating system has been
validated with this project yet. Do not describe them as supported or
tested until the full unlock, mount, file-write, eject, lock, and
read-back workflow has been completed on those systems.

## CLI banner

The Windows desktop CLI displays the following banner at startup:

``` text
╭─────────────────────────────────────────────────────────╮
│                                                         │
│     ____  ___  ___________  _______   _  __             │
│    / __ \/ _ )/ __/  _/ _ \/  _/ _ | / |/ /             │
│   / /_/ / _  |\ \_/ // // // // __ |/    /              │
│   \____/____/___/___/____/___/_/ |_/_/|_/               │
│                                                         │
│                                                         │
│   Created by  Mahmoud Ibrahiem   •  github.com/0x70ta   │
│                                                         │
╰─────────────────────────────────────────────────────────╯
```

## Desktop CLI

The Windows CLI uses Python and these packages:

-   `pyserial`
-   `rich`
-   `pyfiglet`

Example setup in PowerShell:

``` powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install pyserial rich pyfiglet
py cli.py
```

Select the COM port corresponding to **USB Serial Device** for the XIAO
board, not a Bluetooth serial port.

The CLI offers:

1.  Device status
2.  Initialize / format
3.  Unlock decoy
4.  Unlock hidden
5.  Lock
6.  Help
7.  Exit

Close the CLI or release the serial port before opening Arduino Serial
Monitor. Likewise, close Serial Monitor before running the CLI.

## Windows first-use procedure

1.  Unlock a volume from the CLI.
2.  Confirm that Windows enumerates the OBSIDIAN USB Mass Storage
    device.
3.  In Disk Management, verify the disk size and partition belong to the
    OBSIDIAN virtual device. Do not select the physical microSD card.
4.  If the virtual partition is new and has no filesystem, format **only
    the verified OBSIDIAN virtual partition** as exFAT.
5.  Create a small test file.
6.  Use Windows **Safely Remove Hardware / Eject** before locking the
    device.
7.  Lock the device, unlock the same volume again, and verify that the
    test file can be read.

Do not format a disk if its identity is uncertain. Do not unplug the
board or remove the SD card while Windows is writing.

## Diagnostics

The diagnostic firmware may print messages such as:

  ---------------------------------------------------------------------
  Message                            Interpretation
  ---------------------------------- ----------------------------------
  `DIAG_PASSWORD_CHECK=PASS`         Password check succeeded

  `DIAG_MBR_BEGIN`                   Virtual MBR initialization started

  `DIAG_SLOT_UNUSED`                 A slot was treated as unused

  `DIAG_SLOT_AUTH_FAIL`              Slot ciphertext failed GCM
                                     authentication

  `DIAG_BLOCK_NO_VALID_SLOT`         Neither slot was accepted as a
                                     valid or unused block

  `DIAG_MBR_CREATE_WRITE_OK`         Initial virtual MBR was written

  `DIAG_MBR_ALREADY_PRESENT`         A nonblank virtual MBR already
                                     existed

  `UNLOCK_RESULT=SUCCESS`            Logical volume initialized and MSC
                                     start path returned success
  ---------------------------------------------------------------------

`UNLOCK_RESULT=SUCCESS` alone does not prove that Windows can mount a
filesystem or that file read/write persistence works.

## Known limitations and safety notes

This is an experimental prototype. It has not been independently audited
or fully validated.

Known areas requiring work:

-   USB MSC behavior and host cache/eject handling need broader testing.
-   File-system formatting and read/write persistence need to be tested
    on Windows.
-   Power-loss behavior during block updates needs testing.
-   Metadata corruption and recovery behavior need stronger design.
-   The current unused-slot detection has the marker-loss limitation
    described above.
-   The physical button can request a lock; always eject the drive in
    Windows first.
-   No claim of forensic undetectability, plausible deniability, or
    resistance to all forms of analysis is made.
-   Do not store irreplaceable, confidential, or important data on this
    prototype.

## Current next milestone

**Validate filesystem and file persistence:**

-   Format the verified virtual D: partition as exFAT.
-   Write a small test file.
-   Safely eject and lock.
-   Unlock the same volume.
-   Read the file back and compare its contents.
-   Repeat with the hidden volume only after the decoy test is
    understood.

Record the firmware version, SD card, Windows result, and diagnostic
output for each test.

------------------------------------------------------------------------

**Project:** OBSIDIAN\
**Repository/author attribution used in CLI banner:** `0x70ta`\
**Document status:** Project notes based on the current prototype source
and observed session results.

