"""数盟（DUID）设备标识生成。

酷安的写接口（createFeed / reply / like）走服务端下发的 DDI 白名单，
没有 ddid 会返回 status=-10「检测到您的网络环境可能异常」。

数盟协议：合成标识 -> JSON -> zlib 压缩 -> 与固定密钥异或 -> POST 到采集端点，
响应同样逆序解码后取 n_a 字段作为 DUID。

协议参考 kongwufang/szlm_res（MIT）。
只发送新建的合成标识，不读取硬件标识，不携带酷安账号或 Cookie。
"""

from __future__ import annotations

import json
import os
import time
import zlib
from typing import Any

import requests

ENDPOINT = (
    "https://auni.telecome.cn/a/mdna/report"
    "?v=8.7&t=m&p=F9BD0FBDACFE80FCF34370FBCFEE1A98"
    "&r=5bb7efdd4c794f0e9563317b7802b995&n=0&l=2&h=0"
)
KEY = b"xp7j@&!v5]2k#+3z{n9$q^r%[8f1*d4e:c>0l?m/6)yb-=w}"
MAX_RESPONSE = 64 * 1024


def valid_duid(value: str) -> bool:
    """DUID 形如 DU…，只允许字母数字下划线连字符，长度 10~128。"""
    return (
        value.startswith("DU")
        and 10 <= len(value) <= 128
        and all(c.isalnum() or c in "_-" for c in value)
    )


def _new_payload() -> dict[str, Any]:
    random = os.urandom(96)
    now = time.time()
    return {
        "DUv": "com.coolapk.market",
        "3mS": "v9.0.1",
        "AAA": "v1.0",
        "75c": "11e7b222083a4b732b4b14811f6fc05995a01415eb",
        "sfOo": random[:4].hex().upper()[:7],
        "foO": random[4:12].hex()[:15],
        "2cO": f"{int(now)}.{int((now % 1) * 1_000_000_000):09d}",
        "w91": random[12:28].hex().upper(),
        "gEd": random[28:44].hex(),
        "6yY": random[44:76].hex(),
    }


def _xor(data: bytes) -> bytes:
    return bytes(byte ^ KEY[index % len(KEY)] for index, byte in enumerate(data))


def _encode(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("/", "\\/")
    compressor = zlib.compressobj(6)
    body = compressor.compress(raw.encode("utf-8")) + compressor.flush()
    return _xor(body)


def _decode_response(raw: bytes) -> str:
    if len(raw) > MAX_RESPONSE:
        raise ValueError("数盟响应超过大小限制")
    decoded = _xor(raw)
    try:
        json_bytes = zlib.decompress(decoded)
    except zlib.error:
        json_bytes = decoded
    if len(json_bytes) > MAX_RESPONSE:
        raise ValueError("数盟响应超过大小限制")
    value = json.loads(json_bytes.decode("utf-8"))
    device_id = value.get("n_a") or ""
    if not valid_duid(device_id):
        raise ValueError("数盟未返回有效设备 ID，请稍后重试")
    return device_id


def generate(timeout: int = 12, proxy: str | None = None) -> str:
    """向数盟采集端点请求一个新的 DUID。"""
    body = _encode(_new_payload())
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 8.1; TK Watch Build/OPM2.171019.012)",
        "Accept-Encoding": "identity",
    }
    proxies = {"http": proxy, "https": proxy} if proxy else None
    response = requests.post(
        ENDPOINT,
        headers=headers,
        data=body,
        timeout=timeout,
        allow_redirects=False,
        proxies=proxies,
    )
    if not response.ok:
        raise RuntimeError(f"数盟服务返回 HTTP {response.status_code}")
    return _decode_response(response.content)
