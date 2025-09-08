"""
APDU commands and related smart card constants.
"""
# PC/SC GET DATA (UID)
GET_UID_COMMAND: list[int] = [0xFF, 0xCA, 0x00, 0x00, 0x00]
