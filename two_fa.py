import pyotp
import qrcode
import hashlib
from getpass import getpass

def generate_2fa_secret() -> str:
    return pyotp.random_base32()

def verify_otp(secret: str, otp_input: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(otp_input)
