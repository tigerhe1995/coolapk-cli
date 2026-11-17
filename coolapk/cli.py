"""酷安命令行入口。

用法示例：
  python -m coolapk feed --page 1
  python -m coolapk hot
  python -m coolapk search 小米 --type feed
  python -m coolapk topic 酷安
  python -m coolapk user 12345678
  python -m coolapk post "今天天气不错" --image C:\\a.jpg
  python -m coolapk comment 12345678 "说得对"
  python -m coolapk like 12345678
  python -m coolapk login --cookie "SESSID=...; uid=...; token=..."
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import state
from .client import CoolapkClient, CoolapkError, generate_random_device_code

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value: str) -> str:
    """去掉酷安正文里的 HTML 标签与折叠后缀。"""
    text = _TAG_RE.sub("", value)
    text = html.unescape(text)
    text = text.replace("查看更多", "")
    return " ".join(text.split())


def _client() -> CoolapkClient:
    device_code = state.get_device_code()
    if not device_code:
        device_code = generate_random_device_code()
        state.set_device_code(device_code)
    return CoolapkClient(cookie=state.get_cookie(), device_code=device_code)


def _emit(payload: Any, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)


def _brief_feed(item: dict[str, Any]) -> str:
    """把一条动态压成一行摘要。"""
    user = item.get("username") or (item.get("user") or {}).get("username") or "匿名"
    message = _clean_text(str(item.get("message") or item.get("message_text") or ""))
    if len(message) > 80:
        message = message[:80] + "…"
    feed_id = item.get("id") or item.get("entityId") or ""
    return f"[{feed_id}] {user}: {message}"


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
    """首页推荐流是卡片结构，需要把 entities 里的 feed 摊平。"""
    items = _as_list(payload)
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entities = item.get("entities")
        if isinstance(entities, list) and entities:
            for entity in entities:
                if isinstance(entity, dict) and entity.get("id"):
                    result.append(entity)
        elif item.get("id"):
            result.append(item)
    return result


def cmd_feed(args: argparse.Namespace) -> int:
    client = _client()
    feeds = _feed_list(client.index_v8(args.page))
    if args.json:
        _emit(feeds)
        return 0
    for item in feeds:
        print(_brief_feed(item))
    print(f"\n共 {len(feeds)} 条（第 {args.page} 页）")
    return 0


def cmd_hot(args: argparse.Namespace) -> int:
    client = _client()
    items = _as_list(client.hot_feeds(args.page))
    if args.json:
        _emit(items)
        return 0
    for item in items:
        if isinstance(item, dict):
            print(_brief_feed(item))
    print(f"\n共 {len(items)} 条")
    return 0


def cmd_latest(args: argparse.Namespace) -> int:
    client = _client()
    items = _as_list(client.latest_feeds(args.page))
    if args.json:
        _emit(items)
        return 0
    for item in items:
        if isinstance(item, dict):
            print(_brief_feed(item))
    print(f"\n共 {len(items)} 条")
    return 0


def cmd_topic(args: argparse.Namespace) -> int:
    client = _client()
    if args.feeds:
        payload = client.topic_feed_list(args.tag, args.page)
    else:
        payload = client.topic_detail(args.tag)
    _emit(payload)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    client = _client()
    payload = client.search(args.query, args.type, args.page)
    if args.json:
        _emit(payload)
        return 0
    items = _as_list(payload)
    for item in items:
        if isinstance(item, dict):
            print(_brief_feed(item))
    print(f"\n共 {len(items)} 条")
    return 0


def cmd_feed_detail(args: argparse.Namespace) -> int:
    client = _client()
    _emit(client.feed_detail(args.feed_id))
    return 0


def cmd_replies(args: argparse.Namespace) -> int:
    client = _client()
    payload = client.feed_replies(args.feed_id, args.page, args.list_type)
    if args.json:
        _emit(payload)
        return 0
    for item in _as_list(payload):
        if isinstance(item, dict):
            print(_brief_feed(item))
    return 0


def cmd_user(args: argparse.Namespace) -> int:
    client = _client()
    if args.feeds:
        _emit(client.user_feeds(args.uid, args.page))
    else:
        _emit(client.user_profile(args.uid))
    return 0


def cmd_me(args: argparse.Namespace) -> int:
    client = _client()
    if not client.logged_in:
        print("当前未登录。用 `python -m coolapk login --cookie \"SESSID=...\"` 导入凭据。")
        return 2
    _emit(client.check_login_info())
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    client = _client()
    if args.cookie:
        info = client.login_by_cookie(args.cookie)
        state.set_cookie(client.cookie)
        print("登录成功。")
        _emit(info)
        return 0
    if args.mobile:
        if args.vcode:
            client.login_by_mobile(args.mobile, args.vcode)
            state.set_cookie(client.cookie)
            print("登录成功。")
            _emit(client.check_login_info())
            return 0
        client.send_sms_vcode(args.mobile)
        print("验证码已下发，请加 --vcode 重试。")
        return 0
    print("需要 --cookie 或 --mobile 参数。", file=sys.stderr)
    return 2


def cmd_logout(args: argparse.Namespace) -> int:
    state.set_cookie("")
    print("已清除本地 Cookie。")
    return 0


def cmd_post(args: argparse.Namespace) -> int:
    client = _client()
    if not client.logged_in:
        raise CoolapkError("发帖需要先登录")
    result = client.create_feed(
        args.message,
        pic=args.image or "",
        visible_status=-1 if args.private else 1,
        ddid=args.ddid,
        image_paths=args.image_path,
    )
    _emit(result)
    return 0


def cmd_comment(args: argparse.Namespace) -> int:
    client = _client()
    if not client.logged_in:
        raise CoolapkError("评论需要先登录")
    result = client.reply_feed(
        args.feed_id,
        args.message,
        reply_id=args.reply_id,
        ddid=args.ddid,
        image_paths=args.image_path,
    )
    _emit(result)
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    client = _client()
    if not client.logged_in:
        raise CoolapkError("删除需要先登录")
    _emit(client.delete_feed(args.feed_id))
    return 0


def cmd_delete_reply(args: argparse.Namespace) -> int:
    client = _client()
    if not client.logged_in:
        raise CoolapkError("删除需要先登录")
    _emit(client.delete_reply(args.reply_id))
    return 0


def cmd_like(args: argparse.Namespace) -> int:
    client = _client()
    if not client.logged_in:
        raise CoolapkError("点赞需要先登录")
    if args.unlike:
        result = client.unlike_feed(args.feed_id)
    else:
        result = client.like_feed(args.feed_id, ddid=args.ddid)
    _emit(result)
    return 0


def cmd_follow(args: argparse.Namespace) -> int:
    client = _client()
    if not client.logged_in:
        raise CoolapkError("关注需要先登录")
    if args.topic:
        result = client.unfollow_topic(args.target) if args.unfollow else client.follow_topic(args.target)
    else:
        result = client.unfollow_user(args.target) if args.unfollow else client.follow_user(args.target)
    _emit(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coolapk", description="酷安命令行客户端")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出原始数据")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("feed", help="首页推荐流")
    p.add_argument("--page", type=int, default=1)
    p.set_defaults(func=cmd_feed)

    p = sub.add_parser("hot", help="热门榜")
    p.add_argument("--page", type=int, default=1)
    p.set_defaults(func=cmd_hot)

    p = sub.add_parser("latest", help="最新动态")
    p.add_argument("--page", type=int, default=1)
    p.set_defaults(func=cmd_latest)

    p = sub.add_parser("topic", help="话题详情或话题动态")
    p.add_argument("tag")
    p.add_argument("--feeds", action="store_true", help="拉取话题动态列表")
    p.add_argument("--page", type=int, default=1)
    p.set_defaults(func=cmd_topic)

    p = sub.add_parser("search", help="搜索")
    p.add_argument("query")
    p.add_argument("--type", default="all", help="all / feed / user / topic")
    p.add_argument("--page", type=int, default=1)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("detail", help="动态详情")
    p.add_argument("feed_id")
    p.set_defaults(func=cmd_feed_detail)

    p = sub.add_parser("replies", help="评论列表")
    p.add_argument("feed_id")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--list-type", default="lastupdate_desc")
    p.set_defaults(func=cmd_replies)

    p = sub.add_parser("user", help="用户资料或用户动态")
    p.add_argument("uid")
    p.add_argument("--feeds", action="store_true")
    p.add_argument("--page", type=int, default=1)
    p.set_defaults(func=cmd_user)

    p = sub.add_parser("me", help="当前账号信息")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("login", help="登录")
    p.add_argument("--cookie", help="浏览器抓取的完整 Cookie")
    p.add_argument("--mobile", help="手机号")
    p.add_argument("--vcode", help="短信验证码")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("logout", help="清除本地凭据")
    p.set_defaults(func=cmd_logout)

    p = sub.add_parser("post", help="发布动态")
    p.add_argument("message")
    p.add_argument("--image", help="逗号分隔的图片地址")
    p.add_argument("--image-path", action="append", help="本机图片路径（可重复，自动上传）")
    p.add_argument("--private", action="store_true", help="仅自己可见")
    p.add_argument("--ddid", help="写接口 ddid 会话值")
    p.set_defaults(func=cmd_post)

    p = sub.add_parser("comment", help="评论动态")
    p.add_argument("feed_id")
    p.add_argument("message")
    p.add_argument("--reply-id", help="回复某条评论（楼中楼）")
    p.add_argument("--image-path", action="append", help="本机图片路径（可重复）")
    p.add_argument("--ddid")
    p.set_defaults(func=cmd_comment)

    p = sub.add_parser("delete", help="删除自己发布的动态")
    p.add_argument("feed_id")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("delete-reply", help="删除自己发表的评论")
    p.add_argument("reply_id")
    p.set_defaults(func=cmd_delete_reply)

    p = sub.add_parser("like", help="点赞动态")
    p.add_argument("feed_id")
    p.add_argument("--unlike", action="store_true")
    p.add_argument("--ddid")
    p.set_defaults(func=cmd_like)

    p = sub.add_parser("follow", help="关注用户或话题")
    p.add_argument("target", help="uid 或话题名")
    p.add_argument("--topic", action="store_true", help="target 视为话题名")
    p.add_argument("--unfollow", action="store_true")
    p.set_defaults(func=cmd_follow)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except CoolapkError as error:
        print(f"[酷安错误] {error}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001
        print(f"[异常] {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
