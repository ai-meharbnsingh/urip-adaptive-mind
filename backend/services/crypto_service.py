import json

from cryptography.fernet import Fernet

from backend.config import settings


def get_fernet() -> Fernet:
    key = settings.URIP_FERNET_KEY
    if not key:
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_credentials(data: dict) -> bytes:
    f = get_fernet()
    return f.encrypt(json.dumps(data).encode())


def decrypt_credentials(cipher: bytes) -> dict:
    f = get_fernet()
    return json.loads(f.decrypt(cipher).decode())
