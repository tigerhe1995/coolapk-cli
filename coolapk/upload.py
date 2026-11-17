"""酷安图片上传。

流程与官方客户端一致：
  1. POST /v6/upload/ossUploadPrepare 取 OSS 凭证
  2. PUT 直传到 OSS（V1 签名，HMAC-SHA1）
  3. 用 uploadImagePrefix + uploadFileName 拼出提交给 createFeed 的 pic 地址
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from email.utils import formatdate
from pathlib import Path
from typing import Any

import requests

# 官方客户端固定的上传成功回调。
# OSS 的 x-oss-callback 头要求 base64 编码，且签名时用同一个 base64 串参与计算。
OSS_CALLBACK = (
    "eyJjYWxsYmFja0JvZHlUeXBlIjoiYXBwbGljYXRpb25cL2pzb24iLCJjYWxsYmFja0hvc3QiOiJhcGkuY29vbGFway5jb20iLCJjYWxsYmFja1VybCI6Imh0dHBzOlwvXC9hcGkuY29vbGFway5jb21cL3Y2XC9jYWxsYmFja1wvbW9iaWxlT3NzVXBsb2FkU3VjY2Vzc0NhbGxiYWNrP2NoZWNrQXJ0aWNsZUNvdmVyUmVzb2x1dGlvbj0wJnZlcnNpb25Db2RlPTIxMDIwMzEiLCJjYWxsYmFja0JvZHkiOiJ7XCJidWNrZXRcIjoke2J1Y2tldH0sXCJvYmplY3RcIjoke29iamVjdH0sXCJoYXNQcm9jZXNzXCI6JHt4OnZhcjF9fSJ9"
)
OSS_CALLBACK_VAR = "eyJ4OnZhcjEiOiJmYWxzZSJ9"

IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _image_size(data: bytes) -> str:
    """从 JPEG/PNG 头部读出分辨率，官方上传清单需要这个字段。"""
    if data[:2] == b"\xff\xd8":
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
                height = int.from_bytes(data[offset + 5 : offset + 7], "big")
                width = int.from_bytes(data[offset + 7 : offset + 9], "big")
                return f"{width}x{height}"
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                offset += 2
                continue
            length = int.from_bytes(data[offset + 2 : offset + 4], "big")
            offset += 2 + length
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        return f"{width}x{height}"
    return "0x0"


def _upload_file_list(data: bytes, name: str) -> str:
    files = [{
        "name": name,
        "resolution": _image_size(data),
        "md5": hashlib.md5(data).hexdigest(),
        "hdr": 0,
    }]
    return json.dumps(files, separators=(",", ":"))


def _sign(key: str, method: str, content_md5: str, content_type: str, date: str,
          resource: str, security_token: str, with_callback: bool) -> str:
    """OSS V1 签名。"""
    if with_callback:
        canonical = (
            f"{method}\n{content_md5}\n{content_type}\n{date}\n"
            f"x-oss-callback:{OSS_CALLBACK}\n"
            f"x-oss-callback-var:{OSS_CALLBACK_VAR}\n"
            f"x-oss-security-token:{security_token}\n{resource}"
        )
    else:
        canonical = f"{method}\n{content_md5}\n{content_type}\n{date}\nx-oss-security-token:{security_token}\n{resource}"
    digest = hmac.new(key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def upload_image(client, data: bytes, file_name: str, content_type: str, dir_name: str = "feed") -> str:
    """上传图片并返回可直接提交给 createFeed 的 pic 地址。"""
    uid = client.uid
    if not uid:
        raise RuntimeError("未登录，无法上传图片")

    bucket_name = "image" if dir_name in ("feed", "feed_report", "feed_emoji_picture") else dir_name
    feed_type = "feed" if dir_name == "feed" else ""

    prepare = client._post(
        "/v6/upload/ossUploadPrepare",
        query=[],
        form={
            "uploadBucket": bucket_name,
            "uploadDir": dir_name,
            "is_anonymous": "0",
            "uploadFileList": _upload_file_list(data, file_name),
            "toUid": uid,
            "feed_type": feed_type,
        },
    )
    if not isinstance(prepare, dict) or not prepare.get("fileInfo"):
        message = ""
        if isinstance(prepare, dict):
            message = str(prepare.get("message") or prepare.get("error") or "服务端未返回凭证数据")
        raise RuntimeError(f"上传凭证获取失败（{message}）")

    info = prepare["uploadPrepareInfo"]
    file_info = prepare["fileInfo"][0]
    upload_file_name = file_info.get("uploadFileName") or ""
    existing_url = (file_info.get("url") or "").strip()

    prefix = (info.get("uploadImagePrefix") or "http://image.coolapk.com").rstrip("/")
    # 酷安服务端只接受 https 的配图地址，http 会被替换成 placeholder_check.png。
    if prefix.startswith("http://"):
        prefix = "https://" + prefix[len("http://") :]
    if existing_url:
        # 相同 MD5 的文件服务端已存过，直接复用。
        return f"{prefix}/{upload_file_name}"

    end_point = info.get("endPoint") or ""
    access_key_id = info.get("accessKeyId") or ""
    access_key_secret = info.get("accessKeySecret") or ""
    security_token = info.get("securityToken") or ""
    bucket = info.get("bucket") or ""
    if not all((upload_file_name, end_point, access_key_id, access_key_secret, bucket)):
        raise RuntimeError("上传凭证不完整")

    content_md5 = base64.b64encode(hashlib.md5(data).digest()).decode("ascii")
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    resource = f"/{bucket}/{upload_file_name}"
    signature = _sign(
        access_key_secret, "PUT", content_md5, content_type, date, resource, security_token, True
    )
    host = end_point.replace("https://", "").replace("http://", "").rstrip("/")
    oss_url = f"https://{bucket}.{host}/{upload_file_name}"

    headers = {
        "Authorization": f"OSS {access_key_id}:{signature}",
        "Content-MD5": content_md5,
        "Content-Type": content_type,
        "Date": date,
        "x-oss-callback": OSS_CALLBACK,
        "x-oss-callback-var": OSS_CALLBACK_VAR,
        "x-oss-security-token": security_token,
    }
    # OSS 直传必须用干净会话：酷安 API 客户端的默认头（Host: api.coolapk.com 等）
    # 会污染 OSS 的 Host 校验，直接返回 InvalidArgument。
    oss_session = requests.Session()
    oss_session.trust_env = False
    response = oss_session.put(oss_url, headers=headers, data=data, timeout=60)
    if not response.ok:
        raise RuntimeError(f"OSS 直传失败 (HTTP {response.status_code}): {response.text[:200]}")

    # OSS 回调体里带酷安登记后的真实地址，优先用它。
    try:
        callback_body = response.json()
        callback_url = (callback_body.get("data") or {}).get("url")
        if callback_url:
            return _https(callback_url)
    except ValueError:
        pass

    return f"{prefix}/{upload_file_name}"


def _https(url: str) -> str:
    """把 http:// 图床地址升级成 https://，酷安只认 https。"""
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def upload_image_file(client, path: str, dir_name: str = "feed") -> str:
    """从本机文件上传图片。"""
    file_path = Path(path)
    if not file_path.exists():
        raise RuntimeError(f"图片不存在：{path}")
    content_type = IMAGE_TYPES.get(file_path.suffix.lower(), "image/jpeg")
    return upload_image(client, file_path.read_bytes(), file_path.name, content_type, dir_name)
