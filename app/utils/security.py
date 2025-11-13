from passlib.context import CryptContext
from markupsafe import Markup


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def sanitize_text(text: str) -> str:
    return Markup.escape(text)
