"""酷安 Token V3 离线签名器（与 coolapk-desktop 的 Rust 实现同算法）。

算法链路：
  1. 按时间选取 auth blob 中的密码表片段
  2. 组合 APP_ID / 片段 / 设备码 MD5 / 时间戳 / 版本编码
  3. MD5 得到 password
  4. 派生 22 位盐（标准 base64 末位左移 5 位），再按 bcrypt 字母表解成 16 字节
  5. bcrypt(cost=4) 得 23 字节散列，与盐一起组装成 $2y$04$... 密文串
  6. 密文串整体再做一次标准 base64，前缀 "v3"

注意第 4 步：盐字符串用标准 base64 字符表生成，但服务端按 bcrypt 字母表解释，
因此 '+' / '/' 会出现非法字符错误——这正是需要向前探测时间戳的原因。
"""

from __future__ import annotations

import base64
import hashlib
import time
from pathlib import Path

import bcrypt

APP_ID = "com.coolapk.market"
APP_CODE = 2610162

_BLOB_PATH = Path(__file__).with_name("auth_blob.b64")
_AUTH_BLOB = base64.b64decode(_BLOB_PATH.read_text(encoding="utf-8").strip())

_STD_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_BCRYPT_ALPHABET = b"./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _shift_last_base64_char(value: str, shift: int) -> str:
    """把 base64 串最后一个字符在标准字母表里平移 shift 位。"""
    prefix, last = value[:-1], value[-1]
    index = _STD_ALPHABET.index(last.encode("ascii"))
    shifted = (index + shift) % 64
    return prefix + chr(_STD_ALPHABET[shifted])


def _bcrypt_salt_bytes(salt22: str) -> bytes:
    """按 bcrypt 字母表把 22 位盐解成 16 字节原始盐。

    bcrypt 使用自己的 base64 字母表与位序（大端打包），与标准 base64 不同。
    22 个字符 * 6 bit = 132 bit，取前 128 bit 得到 16 字节。
    """
    out = bytearray()
    bits = 0
    bitcount = 0
    for char in salt22:
        index = _BCRYPT_ALPHABET.find(char.encode("ascii"))
        if index < 0:
            raise ValueError(f"salt contains a non-bcrypt character: {char!r}")
        bits = (bits << 6) | index
        bitcount += 6
        if bitcount >= 8:
            bitcount -= 8
            out.append((bits >> bitcount) & 0xFF)
    if len(out) != 16:
        raise ValueError(f"invalid bcrypt salt length: {len(out)}")
    return bytes(out)


def _bcrypt_base64(data: bytes) -> str:
    """用 bcrypt 字母表编码（OpenBSD bcrypt 的位序）。"""
    out: list[str] = []
    for index in range(0, len(data), 3):
        chunk = data[index : index + 3]
        padded = chunk + b"\x00" * (3 - len(chunk))
        b0, b1, b2 = padded[0], padded[1], padded[2]
        out.append(chr(_BCRYPT_ALPHABET[b0 >> 2]))
        out.append(chr(_BCRYPT_ALPHABET[((b0 << 4) | (b1 >> 4)) & 0x3F]))
        if len(chunk) > 1:
            out.append(chr(_BCRYPT_ALPHABET[((b1 << 2) | (b2 >> 6)) & 0x3F]))
        if len(chunk) > 2:
            out.append(chr(_BCRYPT_ALPHABET[b2 & 0x3F]))
    return "".join(out)


def generate_token_at(device_code: str, timestamp: int, app_code: int = APP_CODE) -> str:
    """生成指定时间戳的 v3 token。"""
    index = ((timestamp + app_code) % 100) * 4 + 0x80
    chunk = _AUTH_BLOB[index : index + 0x80]
    segment = base64.b64decode(chunk).decode("utf-8", errors="replace")

    device_md5 = md5_hex(device_code.encode("utf-8"))
    plain = f"{APP_ID}&{segment}&{device_md5}&{timestamp}&{app_code}"
    plain_md5 = md5_hex(plain.encode("utf-8"))

    password = md5_hex(base64.b64encode(plain.encode("utf-8")))

    salt_source = (
        base64.b64encode(f"{timestamp:x}/{plain_md5}".encode("utf-8")).decode("ascii").rstrip("=")
    )
    salt22 = _shift_last_base64_char(salt_source[:22], -5)
    salt = _bcrypt_salt_bytes(salt22)

    # py-bcrypt 只接受 2a/2b 前缀，先用它算散列，再按 Rust 侧的 2y 格式重组。
    salt_str = "$2b$04$" + _bcrypt_base64(salt)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt_str.encode("ascii"))
    body = hashed.decode("ascii")[7:]  # 去掉 "$2b$04$"

    crypt_string = f"$2y$04${body}"
    return "v3" + base64.b64encode(crypt_string.encode("utf-8")).decode("ascii").rstrip("=")


def get_app_token(device_code: str, app_code: int = APP_CODE) -> str:
    """生成当前时间有效的 v3 token。

    某些时间点派生的 22 位盐不满足 bcrypt 字符表，最多向前探测 15 秒。
    """
    timestamp = int(time.time())
    last_error: Exception | None = None
    for offset in range(0, 16):
        try:
            return generate_token_at(device_code, timestamp + offset, app_code)
        except Exception as error:  # noqa: BLE001 - 逐秒回退
            last_error = error
    raise RuntimeError(f"failed to generate Coolapk token: {last_error}")
