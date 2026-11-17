"""酷安 MCP 服务（stdio）。

暴露酷安读写工具给 MCP 客户端（DSH / Claude Code / Cursor 等）：
  coolapk_health / coolapk_me / coolapk_feed / coolapk_hot / coolapk_search /
  coolapk_feed_detail / coolapk_feed_replies / coolapk_user / coolapk_user_feeds /
  coolapk_topic / coolapk_post / coolapk_comment / coolapk_like /
  coolapk_follow_user / coolapk_follow_topic / coolapk_logout

不依赖第三方 MCP 框架，直接实现 JSON-RPC 2.0 stdio 协议，
避免额外依赖与安装步骤。
"""

from __future__ import annotations

import html
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coolapk import state  # noqa: E402
from coolapk.client import CoolapkClient, CoolapkError, generate_random_device_code  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "coolapk", "version": "1.0.0"}

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value: str) -> str:
    """去掉酷安正文里的 HTML 标签与折叠后缀。"""
    text = _TAG_RE.sub("", value)
    text = html.unescape(text)
    text = text.replace("查看更多", "")
    return " ".join(text.split())

TOOLS: list[dict[str, Any]] = [
    {
        "name": "coolapk_health",
        "description": "查看酷安客户端状态：是否登录、当前 uid、设备码、凭据位置。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "coolapk_me",
        "description": "获取当前登录的酷安账号资料。未登录时返回错误提示。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "coolapk_feed",
        "description": "拉取酷安首页推荐动态流。page 从 1 开始。返回动态列表，含 id、作者、正文。",
        "inputSchema": {
            "type": "object",
            "properties": {"page": {"type": "integer", "minimum": 1, "description": "页码，默认 1"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_hot",
        "description": "拉取酷安热门榜（7 天点赞榜）。page 从 1 开始。",
        "inputSchema": {
            "type": "object",
            "properties": {"page": {"type": "integer", "minimum": 1, "description": "页码，默认 1"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_latest",
        "description": "拉取酷安最新动态流。page 从 1 开始。",
        "inputSchema": {
            "type": "object",
            "properties": {"page": {"type": "integer", "minimum": 1, "description": "页码，默认 1"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_search",
        "description": "搜索酷安内容。type 可取 all / feed / user / topic，默认 all。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜索关键词"},
                "type": {"type": "string", "description": "搜索类型：all / feed / user / topic"},
                "page": {"type": "integer", "minimum": 1, "description": "页码，默认 1"},
            },
            "required": ["q"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_feed_detail",
        "description": "获取单条动态详情。正文、作者、互动数据。",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "动态 ID"}},
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_feed_replies",
        "description": "获取动态的评论列表。listType 可取 lastupdate_desc / dateline_desc / popular。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "动态 ID"},
                "page": {"type": "integer", "minimum": 1, "description": "页码，默认 1"},
                "listType": {"type": "string", "description": "排序方式，默认 lastupdate_desc"},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_user",
        "description": "获取酷安用户资料。",
        "inputSchema": {
            "type": "object",
            "properties": {"uid": {"type": "string", "description": "用户 uid"}},
            "required": ["uid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_user_feeds",
        "description": "获取指定用户发布的动态列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "用户 uid"},
                "page": {"type": "integer", "minimum": 1, "description": "页码，默认 1"},
            },
            "required": ["uid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_topic",
        "description": "获取话题详情或话题下的动态列表。feeds=true 时返回动态列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {"type": "string", "description": "话题名，可带 #"},
                "feeds": {"type": "boolean", "description": "true 返回话题动态列表，默认返回话题详情"},
                "page": {"type": "integer", "minimum": 1, "description": "页码，默认 1"},
            },
            "required": ["tag"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_post",
        "description": "发布一条酷安动态（需要登录）。message 为正文，image 为逗号分隔的图片地址，"
        "imagePaths 为本机图片路径（自动上传）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "动态正文，最多 5000 字，可含 #话题#"},
                "image": {"type": "string", "description": "逗号分隔的图片地址（可选）"},
                "imagePaths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "本机图片绝对路径列表（JPEG/PNG/WebP），自动上传后作为配图",
                },
                "private": {"type": "boolean", "description": "true 表示仅自己可见"},
                "ddid": {"type": "string", "description": "写接口 ddid 会话值（可选，默认自动获取）"},
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_comment",
        "description": "评论一条酷安动态（需要登录）。带 replyId 时是回复某条评论（楼中楼）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feedId": {"type": "string", "description": "被评论的动态 ID"},
                "message": {"type": "string", "description": "评论正文，最多 1000 字"},
                "replyId": {"type": "string", "description": "回复的目标评论 ID（可选）"},
                "imagePaths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "本机图片绝对路径列表，自动上传后作为评论配图",
                },
                "ddid": {"type": "string", "description": "写接口 ddid 会话值（可选，默认自动获取）"},
            },
            "required": ["feedId", "message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_like",
        "description": "点赞或取消点赞一条酷安动态（需要登录）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feedId": {"type": "string", "description": "动态 ID"},
                "unlike": {"type": "boolean", "description": "true 取消点赞，默认点赞"},
                "ddid": {"type": "string", "description": "写接口 ddid 会话值（可选）"},
            },
            "required": ["feedId"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_delete_feed",
        "description": "删除自己发布的酷安动态（不可恢复，需要登录）。",
        "inputSchema": {
            "type": "object",
            "properties": {"feedId": {"type": "string", "description": "要删除的动态 ID"}},
            "required": ["feedId"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_delete_reply",
        "description": "删除自己发表的酷安评论（不可恢复，需要登录）。",
        "inputSchema": {
            "type": "object",
            "properties": {"replyId": {"type": "string", "description": "要删除的评论 ID"}},
            "required": ["replyId"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_follow_user",
        "description": "关注或取关一个酷安用户（需要登录）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "用户 uid"},
                "unfollow": {"type": "boolean", "description": "true 取关，默认关注"},
            },
            "required": ["uid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_follow_topic",
        "description": "关注或取关一个酷安话题（需要登录）。tag 可带 #。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {"type": "string", "description": "话题名"},
                "unfollow": {"type": "boolean", "description": "true 取关，默认关注"},
            },
            "required": ["tag"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_login",
        "description": "导入酷安 Cookie 完成登录。cookie 为浏览器 www.coolapk.com 请求头里的完整 Cookie 串，"
        "必须含 SESSID。成功后凭据保存在本机。",
        "inputSchema": {
            "type": "object",
            "properties": {"cookie": {"type": "string", "description": "完整 Cookie 串"}},
            "required": ["cookie"],
            "additionalProperties": False,
        },
    },
    {
        "name": "coolapk_logout",
        "description": "清除本机保存的酷安登录凭据。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def _client() -> CoolapkClient:
    device_code = state.get_device_code()
    if not device_code:
        device_code = generate_random_device_code()
        state.set_device_code(device_code)
    return CoolapkClient(cookie=state.get_cookie(), device_code=device_code)


def _as_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("list", "items", "entities", "feeds"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _feed_list(payload: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(payload):
        if not isinstance(item, dict):
            continue
        entities = item.get("entities")
        if isinstance(entities, list) and entities:
            result.extend(e for e in entities if isinstance(e, dict) and e.get("id"))
        elif item.get("id"):
            result.append(item)
    return result


def _slim_feed(item: dict[str, Any]) -> dict[str, Any] | None:
    """裁剪动态字段，只保留常用信息，避免把整个响应塞进上下文。

    首页推荐流里混着产品卡片（entityType=product），没有正文与作者，
    对刷酷安没有价值，直接丢掉。
    """
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    message = _clean_text(str(item.get("message") or ""))
    username = item.get("username") or user.get("username")
    feed_id = item.get("id")
    if not message.strip() and not username:
        return None
    return {
        "id": feed_id,
        "uid": item.get("uid") or user.get("uid"),
        "username": username,
        "message": message[:600],
        "messageTruncated": len(message) > 600,
        "likeNum": item.get("like_num", item.get("likenum")),
        "replyNum": item.get("reply_num", item.get("replynum")),
        "forwardNum": item.get("forward_num"),
        "dateline": item.get("dateline"),
        "url": item.get("url"),
    }


def _tool_health(_: dict[str, Any]) -> Any:
    client = _client()
    return {
        "loggedIn": client.logged_in,
        "uid": client.uid,
        "deviceCode": client.device_code[:16] + "…",
        "stateFile": str(state.STATE_FILE),
        "serverVersion": SERVER_INFO["version"],
    }


def _tool_me(_: dict[str, Any]) -> Any:
    client = _client()
    if not client.logged_in:
        raise CoolapkError("当前未登录，请先调用 coolapk_login 导入 Cookie")
    return client.check_login_info()


def _tool_feed(args: dict[str, Any]) -> Any:
    client = _client()
    feeds = _feed_list(client.index_v8(int(args.get("page", 1))))
    result = [_slim_feed(f) for f in feeds]
    return [item for item in result if item]


def _tool_hot(args: dict[str, Any]) -> Any:
    client = _client()
    items = _as_list(client.hot_feeds(int(args.get("page", 1))))
    result = [_slim_feed(f) for f in items if isinstance(f, dict)]
    return [item for item in result if item]


def _tool_latest(args: dict[str, Any]) -> Any:
    client = _client()
    items = _as_list(client.latest_feeds(int(args.get("page", 1))))
    result = [_slim_feed(f) for f in items if isinstance(f, dict)]
    return [item for item in result if item]


def _slim_reply(item: dict[str, Any]) -> dict[str, Any] | None:
    """裁剪评论字段。"""
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    message = _clean_text(str(item.get("message") or ""))
    reply_id = item.get("id")
    username = item.get("username") or user.get("username")
    if not message.strip() and not username:
        return None
    return {
        "id": reply_id,
        "uid": item.get("uid") or user.get("uid"),
        "username": username,
        "message": message[:400],
        "likeNum": item.get("like_num", item.get("likenum")),
        "replyNum": item.get("reply_num", item.get("replynum")),
        "ruid": item.get("ruid"),
        "rusername": item.get("rusername"),
        "isFeedAuthor": item.get("isFeedAuthor"),
        "dateline": item.get("dateline"),
    }


def _tool_search(args: dict[str, Any]) -> Any:
    client = _client()
    search_type = args.get("type", "all")
    page = int(args.get("page", 1))
    payload = client.search(args["q"], search_type, page)
    items = _as_list(payload)
    if not items:
        return []
    # 搜索命中可能是动态、用户、话题或应用卡片；统一裁成精简条目。
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("entityType") == "feed" or item.get("message") is not None:
            slim = _slim_feed(item)
            if slim:
                result.append(slim)
                continue
        result.append(
            {
                "entityType": item.get("entityType"),
                "entityId": item.get("entityId"),
                "title": item.get("title"),
                "url": item.get("url"),
                "description": str(item.get("description") or "")[:300],
                "username": item.get("username"),
                "uid": item.get("uid"),
            }
        )
    return result


def _tool_feed_detail(args: dict[str, Any]) -> Any:
    client = _client()
    payload = client.feed_detail(args["id"])
    if not isinstance(payload, dict):
        return payload
    if payload.get("guestOnly"):
        return payload
    slim = _slim_feed(payload)
    detail = slim or {}
    # 详情里评论预览、点赞列表、关联推荐、广告卡片体量很大，单独丢弃。
    for key in (
        "replyRows", "top_reply_ids", "topReplyRows", "recent_like_list",
        "relateddata", "userInfo", "detailSponsorCard", "relationRows",
        "raw", "targetRow", "userAction", "shareUrl", "message_raw_output",
    ):
        payload.pop(key, None)
    detail["picArr"] = payload.get("picArr") or payload.get("pic") or ""
    detail["tags"] = payload.get("tags", "")
    detail["messageTitle"] = payload.get("message_title", "")
    detail["deviceTitle"] = payload.get("device_title", "")
    detail["ipLocation"] = payload.get("ip_location", "")
    detail["enableModify"] = payload.get("enableModify")
    return detail


def _tool_feed_replies(args: dict[str, Any]) -> Any:
    client = _client()
    payload = client.feed_replies(
        args["id"], int(args.get("page", 1)), args.get("listType", "lastupdate_desc")
    )
    items = _as_list(payload)
    result = [_slim_reply(r) for r in items if isinstance(r, dict)]
    return [r for r in result if r]


def _tool_user(args: dict[str, Any]) -> Any:
    client = _client()
    payload = client.user_profile(args["uid"])
    if not isinstance(payload, dict):
        return payload
    return {
        "uid": payload.get("uid"),
        "username": payload.get("username"),
        "userAvatar": payload.get("userAvatar"),
        "level": payload.get("level"),
        "experience": payload.get("experience"),
        "follow": payload.get("follow"),
        "fans": payload.get("fans"),
        "feed": payload.get("feed"),
        "like": payload.get("like"),
        "regdate": payload.get("regdate"),
        "bio": str(payload.get("bio") or "")[:300],
        "url": payload.get("url"),
    }


def _tool_user_feeds(args: dict[str, Any]) -> Any:
    client = _client()
    payload = client.user_feeds(args["uid"], int(args.get("page", 1)))
    items = _as_list(payload)
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slim = _slim_feed(item)
        if slim:
            result.append(slim)
        # 二手动态的价格与链接信息在 ershou_info 里，单独带出来。
        ershou = item.get("ershou_info")
        if isinstance(ershou, dict) and result:
            result[-1]["ershou"] = {
                "productTitle": ershou.get("product_title"),
                "price": ershou.get("product_price"),
                "city": ershou.get("city"),
                "province": ershou.get("province"),
                "status": ershou.get("ershou_status"),
            }
    return result


def _tool_topic(args: dict[str, Any]) -> Any:
    client = _client()
    tag = str(args["tag"]).strip().strip("#")
    if args.get("feeds"):
        payload = client.topic_feed_list(tag, int(args.get("page", 1)))
        items = _as_list(payload)
        result = [_slim_feed(f) for f in items if isinstance(f, dict)]
        return [f for f in result if f]
    payload = client.topic_detail(tag)
    if not isinstance(payload, dict):
        return payload
    return {
        "id": payload.get("id"),
        "title": payload.get("title"),
        "logo": payload.get("logo"),
        "description": str(payload.get("description") or "")[:400],
        "follow_num": payload.get("follow_num", payload.get("followNum")),
        "ttitle": payload.get("ttitle"),
        "url": payload.get("url"),
    }


def _require_login(client: CoolapkClient) -> None:
    if not client.logged_in:
        raise CoolapkError("该操作需要先登录，请调用 coolapk_login 导入 Cookie")


def _write_result(payload: Any) -> Any:
    """写操作的返回只保留关键字段，避免整份服务端响应塞进上下文。"""
    if not isinstance(payload, dict):
        return payload
    return {
        "id": payload.get("id"),
        "uid": payload.get("uid"),
        "username": payload.get("username"),
        "message": _clean_text(str(payload.get("message") or ""))[:300],
        "pic": payload.get("pic"),
        "picArr": payload.get("picArr"),
        "url": payload.get("url"),
        "dateline": payload.get("dateline"),
        "fid": payload.get("fid"),
        "rid": payload.get("rid"),
        "status": payload.get("status"),
    }


def _tool_post(args: dict[str, Any]) -> Any:
    client = _client()
    _require_login(client)
    return _write_result(client.create_feed(
        args["message"],
        pic=args.get("image") or "",
        visible_status=-1 if args.get("private") else 1,
        ddid=args.get("ddid"),
        image_paths=args.get("imagePaths"),
    ))


def _tool_comment(args: dict[str, Any]) -> Any:
    client = _client()
    _require_login(client)
    return _write_result(client.reply_feed(
        args["feedId"],
        args["message"],
        reply_id=args.get("replyId"),
        ddid=args.get("ddid"),
        image_paths=args.get("imagePaths"),
    ))


def _tool_like(args: dict[str, Any]) -> Any:
    client = _client()
    _require_login(client)
    if args.get("unlike"):
        return client.unlike_feed(args["feedId"])
    return client.like_feed(args["feedId"], ddid=args.get("ddid"))


def _tool_delete_feed(args: dict[str, Any]) -> Any:
    client = _client()
    _require_login(client)
    return client.delete_feed(args["feedId"])


def _tool_delete_reply(args: dict[str, Any]) -> Any:
    client = _client()
    _require_login(client)
    return client.delete_reply(args["replyId"])


def _tool_follow_user(args: dict[str, Any]) -> Any:
    client = _client()
    _require_login(client)
    if args.get("unfollow"):
        return client.unfollow_user(args["uid"])
    return client.follow_user(args["uid"])


def _tool_follow_topic(args: dict[str, Any]) -> Any:
    client = _client()
    _require_login(client)
    if args.get("unfollow"):
        return client.unfollow_topic(args["tag"])
    return client.follow_topic(args["tag"])


def _tool_login(args: dict[str, Any]) -> Any:
    client = _client()
    info = client.login_by_cookie(args["cookie"])
    state.set_cookie(client.cookie)
    return {"ok": True, "uid": client.uid, "profile": info}


def _tool_logout(_: dict[str, Any]) -> Any:
    state.set_cookie("")
    return {"ok": True}


HANDLERS = {
    "coolapk_health": _tool_health,
    "coolapk_me": _tool_me,
    "coolapk_feed": _tool_feed,
    "coolapk_hot": _tool_hot,
    "coolapk_latest": _tool_latest,
    "coolapk_search": _tool_search,
    "coolapk_feed_detail": _tool_feed_detail,
    "coolapk_feed_replies": _tool_feed_replies,
    "coolapk_user": _tool_user,
    "coolapk_user_feeds": _tool_user_feeds,
    "coolapk_topic": _tool_topic,
    "coolapk_post": _tool_post,
    "coolapk_comment": _tool_comment,
    "coolapk_like": _tool_like,
    "coolapk_delete_feed": _tool_delete_feed,
    "coolapk_delete_reply": _tool_delete_reply,
    "coolapk_follow_user": _tool_follow_user,
    "coolapk_follow_topic": _tool_follow_topic,
    "coolapk_login": _tool_login,
    "coolapk_logout": _tool_logout,
}


def _text_result(payload: Any, is_error: bool = False) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": _text_result(f"未知工具：{name}", is_error=True),
            }
        try:
            return {"jsonrpc": "2.0", "id": request_id, "result": _text_result(handler(arguments))}
        except CoolapkError as error:
            return {"jsonrpc": "2.0", "id": request_id, "result": _text_result(str(error), is_error=True)}
        except Exception as error:  # noqa: BLE001
            detail = traceback.format_exc(limit=3)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": _text_result(f"{type(error).__name__}: {error}\n{detail}", is_error=True),
            }
    if method and method.startswith("notifications/"):
        return None
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_request(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
