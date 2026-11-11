"""Passcode encryption that the phone can undo with the browser's built-in WebCrypto.

Format (JSON): {"v":1,"kdf":"PBKDF2-SHA256","iter":N,"salt":b64,"iv":b64,"ct":b64}
AES-256-GCM; ct includes the 16-byte auth tag at the end (what WebCrypto expects).
"""
import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 600_000
AAD = b"dead-ahead:v1"


def _key(passcode: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(passcode.encode("utf-8"))


def encrypt(obj, passcode: str) -> dict:
    salt, iv = os.urandom(16), os.urandom(12)
    plaintext = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ct = AESGCM(_key(passcode, salt, ITERATIONS)).encrypt(iv, plaintext, AAD)
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITERATIONS, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def decrypt(blob: dict, passcode: str):
    if blob.get("v") != 1:
        raise ValueError("Unknown encrypted format version")
    d = lambda k: base64.b64decode(blob[k])
    key = _key(passcode, d("salt"), int(blob["iter"]))
    plaintext = AESGCM(key).decrypt(d("iv"), d("ct"), AAD)  # raises InvalidTag on wrong passcode
    return json.loads(plaintext)
