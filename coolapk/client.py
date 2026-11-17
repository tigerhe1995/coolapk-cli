"""酷安 API 客户端（Python）。

端点、请求头与签名算法对齐 coolapk-desktop（Rust 客户端），可直接使用
酷安官方接口。游客态可读公开内容；登录后支持发帖、评论、点赞、关注等写操作。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlencode

import requests

from .auth import APP_CODE, get_app_token

API_ORIGIN = "https://api.coolapk.com"
API_ORIGIN_ALT = "https://api2.coolapk.com"

APP_VERSION = "16.6.5"
APP_ID = "com.coolapk.market"
COMPATIBILITY_UA = (
    "Dalvik/2.1.0 (Linux; U; Android 16; 23113RKC6C Build/AQ3A.250226.002) "
    "(#Build; Redmi; 23113RKC6C; AQ3A.250226.002; 16) "
    "+CoolMarket/16.6.5-2610162-universal"
)

DEFAULT_MODEL = "23113RKC6C"
DEFAULT_BUILD = "AQ3A.250226.002"

# 官方 createFeed 表单字段顺序（与 APK 一致，缺字段会被服务端忽略）
CREATE_FEED_FIELDS: tuple[tuple[str, str], ...] = (
    ("id", ""),
    ("message", ""),
    ("type", "feed"),
    ("pic", ""),
    ("status", "1"),
    ("publish_status", "0"),
    ("location", ""),
    ("long_location", ""),
    ("latitude", "0.0"),
    ("longitude", "0.0"),
    ("media_url", ""),
    ("media_type", "0"),
    ("media_pic", ""),
    ("message_title", ""),
    ("message_brief", ""),
    ("extra_title", ""),
    ("extra_url", ""),
    ("extra_key", ""),
    ("extra_pic", ""),
    ("extra_info", ""),
    ("message_cover", ""),
    ("original_type", "0"),
    ("is_editInDyh", "0"),
    ("forwardid", ""),
    ("fid", ""),
    ("dyhId", ""),
    ("targetType", ""),
    ("productId", ""),
    ("targetId", ""),
    ("location_city", ""),
    ("location_country", ""),
    ("disallow_reply", "0"),
    ("vote_score", "0"),
    ("replyWithForward", "0"),
    ("media_info", ""),
    ("insert_product_media", "0"),
    ("is_ks_doc", "0"),
    ("goods_list_id", ""),
    ("is_html_article", "0"),
)

# 需要携带 ddid 会话 Cookie 的写接口
DDI_EVENT_PATHS = ("/v6/feed/createFeed", "/v6/feed/reply", "/v6/feed/like", "/v6/feed/likeReply")


class CoolapkError(RuntimeError):
    """酷安接口返回的业务错误。"""

    def __init__(self, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.payload = payload

    @property
    def is_captcha(self) -> bool:
        text = str(self)
        return "captcha" in text.lower() or "验证" in text


def _reverse_base64_code(raw: str) -> str:
    """酷安设备码格式：Base64 编码后逆序并去掉 '=' 填充。"""
    import base64

    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return "".join(reversed(encoded)).replace("=", "")


def _decode_device_code(code: str) -> list[str]:
    import base64

    reversed_code = code[::-1]
    padding = (4 - len(reversed_code) % 4) % 4
    try:
        raw = base64.b64decode(reversed_code + "=" * padding).decode("utf-8")
    except Exception:  # noqa: BLE001 - 设备码可能来自外部配置
        return []
    return [part.strip() for part in raw.split(";")]


def generate_random_device_code() -> str:
    """生成游客设备码（首次生成后应持久化，避免每次换设备指纹）。"""
    seed = f"{time.time_ns()}-{os.getpid()}-{uuid.uuid4().hex}"
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    android_id = f"{int.from_bytes(digest[:8], 'little'):016x}"
    raw = f"{android_id}; ; ; ; Xiaomi; Xiaomi; {DEFAULT_MODEL}; UKQ1.230804.001; "
    return _reverse_base64_code(raw)


def device_code_for_uid(uid: str) -> str:
    """按 uid 派生账号设备码（与官方客户端 v1.9.1 之前的算法一致）。"""
    digest = hashlib.md5(uid.encode("utf-8")).digest()
    android_id = f"{int.from_bytes(digest[:8], 'little'):016x}"
    raw = f"{android_id}; ; ; ; Xiaomi; Xiaomi; {DEFAULT_MODEL}; UKQ1.230804.001; "
    return _reverse_base64_code(raw)


def device_code_with_model(code: str, model: str = DEFAULT_MODEL, build: str = DEFAULT_BUILD) -> str:
    """把设备码里的机型/Build 段替换成指定值。"""
    fields = _decode_device_code(code)
    if len(fields) != 9:
        return code
    fields[4] = "Xiaomi"
    fields[5] = "Xiaomi"
    fields[6] = model
    fields[7] = build
    return _reverse_base64_code("; ".join(fields))


def device_code_with_duid(duid: str, model: str = DEFAULT_MODEL, build: str = DEFAULT_BUILD) -> str:
    """用数盟 DUID 作首字段生成设备码。

    酷安写接口会校验设备码首字段是否为有效的数盟设备 ID：
    首字段不是 DUID 时 createFeed / reply / like 一律返回 status=-10
    「检测到您的网络环境可能异常」。
    """
    raw = f"{duid}; ; ; ; Xiaomi; Xiaomi; {model}; {build}; "
    return _reverse_base64_code(raw)


def sanitize_cookie(cookie: str) -> str:
    """清理 Cookie：去空白、合并重复键。"""
    entries: list[str] = []
    seen: set[str] = set()
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name = part.split("=", 1)[0].strip()
        if not name or name in seen:
            continue
        seen.add(name)
        entries.append(part)
    return "; ".join(entries)


def _cookie_without_ddid(cookie: str) -> str:
    return "; ".join(
        part.strip()
        for part in cookie.split(";")
        if part.strip() and part.split("=", 1)[0].strip().lower() != "ddid"
    )


class CoolapkClient:
    """酷安接口客户端。

    登录态由 cookie 提供（SESSID / uid / token 等字段），
    也可以直接用手机号+验证码或账号密码登录后自动保存。
    """

    def __init__(
        self,
        cookie: str | None = None,
        device_code: str | None = None,
        timeout: int = 20,
        proxy: str | None = None,
    ) -> None:
        self.cookie = sanitize_cookie(cookie or "")
        self.device_code = device_code or generate_random_device_code()
        self.timeout = timeout
        self._ddid_cache: str | None = None
        self._duid_cache: str | None = None
        self.session = requests.Session()
        self.session.trust_env = True
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    # ---------- 基础 ----------

    @property
    def uid(self) -> str | None:
        for part in self.cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name.strip() == "uid" and value.strip():
                return value.strip()
        return None

    @property
    def logged_in(self) -> bool:
        return bool(self.uid) and "SESSID=" in self.cookie

    def set_cookie(self, cookie: str) -> None:
        self.cookie = sanitize_cookie(cookie)

    def _ddid(self, path: str, explicit: str | None = None) -> str | None:
        """写接口需要的 ddid 会话值。

        酷安服务端下发的 useDDIEventList 覆盖 createFeed / reply / like /
        likeReply；缺少 ddid 时这些接口返回 status=-10「网络环境可能异常」。
        """
        if not path.startswith(DDI_EVENT_PATHS):
            return None
        if explicit and explicit.strip():
            return explicit.strip()
        # 与设备码首字段共用同一个 DUID，保持设备身份一致。
        duid = self._device_id()
        if duid:
            self._ddid_cache = duid
        return self._ddid_cache

    def _device_id(self) -> str | None:
        """当前会话的数盟 DUID（设备码首字段与 ddid cookie 共用同一个值）。"""
        if self._duid_cache:
            return self._duid_cache
        try:
            from .shuzilm import generate

            self._duid_cache = generate()
        except Exception:  # noqa: BLE001 - 取不到就退回 uid 派生设备码
            return None
        return self._duid_cache

    def _effective_device_code(self, guest: bool = False) -> str:
        """当前请求使用的设备码。

        登录态用数盟 DUID 作首字段：写接口会校验设备码首字段，
        不是有效 DUID 时一律返回 status=-10。
        读接口无此要求，但沿用同一设备码以保持会话指纹一致。
        """
        if not guest:
            duid = self._device_id()
            if duid:
                return device_code_with_duid(duid)
        uid = None if guest else self.uid
        if uid:
            return device_code_with_model(device_code_for_uid(uid))
        return device_code_with_model(self.device_code)

    def _headers(self, token: str, device_code: str) -> dict[str, str]:
        return {
            "User-Agent": COMPATIBILITY_UA,
            "X-Requested-With": "XMLHttpRequest",
            "X-App-Token": token,
            "X-App-Device": device_code,
            "X-App-Id": APP_ID,
            "X-App-Version": APP_VERSION,
            "X-App-Code": str(APP_CODE),
            "X-App-Supported": str(APP_CODE),
            "X-App-Channel": "coolapk",
            "X-App-Mode": "universal",
            "X-Api-Version": "16",
            "X-Sdk-Int": "36",
            "X-Sdk-Locale": "zh-CN",
            "X-Dark-Mode": "0",
            "Accept": "application/json",
        }

    def _cookie_header(self, path: str) -> str | None:
        if not self.cookie:
            return None
        cookie = _cookie_without_ddid(self.cookie)
        if path.startswith(DDI_EVENT_PATHS):
            cookie = cookie  # ddid 由调用方可选注入
        return cookie or None

    def _request(
        self,
        method: str,
        path: str,
        query: Iterable[tuple[str, str]] | None = None,
        form: dict[str, str] | None = None,
        origin: str = API_ORIGIN,
        guest: bool = False,
        ddid: str | None = None,
    ) -> Any:
        # 登录态必须使用账号绑定的设备码：Token V3 与设备码绑定，
        # 游客设备码配账号 Cookie 会被服务端判定为异常请求。
        device_code = self._effective_device_code(guest=guest)
        token = get_app_token(device_code)
        headers = self._headers(token, device_code)
        url = f"{origin}{path}"
        if query:
            url = f"{url}?{urlencode(list(query))}"

        cookies: dict[str, str] | None = None
        if not guest and self.cookie:
            raw = _cookie_without_ddid(self.cookie)
            ddid_value = self._ddid(path, ddid)
            if ddid_value:
                encoded = quote(ddid_value, safe="")
                raw = f"{raw}; ddid={encoded}" if raw else f"ddid={encoded}"
            cookies = {}
            for part in raw.split(";"):
                if "=" in part:
                    name, _, value = part.strip().partition("=")
                    cookies[name.strip()] = value.strip()

        response = self.session.request(
            method,
            url,
            headers=headers,
            cookies=cookies,
            data=form,
            timeout=self.timeout,
        )
        try:
            payload = response.json()
        except ValueError:
            raise CoolapkError(f"酷安接口返回非 JSON（HTTP {response.status_code}）") from None
        return self._unwrap(payload)

    @staticmethod
    def _unwrap(payload: Any) -> Any:
        """按官方信封判定成功，失败时抛出 CoolapkError。"""
        if not isinstance(payload, dict):
            return payload
        error = payload.get("error")
        if isinstance(error, str) and error and error != "0":
            raise CoolapkError(error, payload)

        message = payload.get("message")
        if isinstance(message, str) and message:
            code = payload.get("code")
            try:
                code_value = int(code) if code is not None else 200
            except (TypeError, ValueError):
                code_value = 200
            status = payload.get("status")
            status_value = status if isinstance(status, int) else 1
            message_status = payload.get("messageStatus")
            message_status = message_status if isinstance(message_status, str) else ""
            if message_status == "err_request_captcha_v2" or payload.get("messageExtra") is not None:
                raise CoolapkError(json.dumps(payload, ensure_ascii=False), payload)
            if code_value not in (200, 0, 1) or status_value not in (0, 1) or message_status.startswith("err_"):
                raise CoolapkError(message, payload)

        status = payload.get("status")
        if isinstance(status, int) and status < 0:
            detail = payload.get("message") or payload.get("error") or "酷安服务端拒绝请求"
            raise CoolapkError(str(detail), payload)

        return payload.get("data", payload)

    def _get(self, path: str, query: Iterable[tuple[str, str]] | None = None, **kwargs) -> Any:
        return self._request("GET", path, query=query, **kwargs)

    def _get_with_fallback(self, path: str, query: Iterable[tuple[str, str]] | None = None) -> Any:
        """GET 请求，遇验证码风控时换 api2 主机再试一次。

        酷安对同一个游客设备码的某些端点会弹验证码，但 api2 路由通常放行，
        与官方桌面客户端的公开内容回退策略一致。
        """
        query = list(query or [])
        try:
            return self._request("GET", path, query=query)
        except CoolapkError as error:
            if not error.is_captcha:
                raise
            return self._request("GET", path, query=query, origin=API_ORIGIN_ALT)

    def _post(self, path: str, query=None, form=None, **kwargs) -> Any:
        return self._request("POST", path, query=query, form=form, **kwargs)

    # ---------- 登录 ----------

    def send_sms_vcode(self, mobile: str) -> Any:
        return self._post("/v6/account/sendVcode", form={"mobile": mobile, "type": "login"})

    def login_by_mobile(self, mobile: str, vcode: str) -> Any:
        data = self._post(
            "/v6/account/loginByMobile",
            form={"mobile": mobile, "vcode": vcode, "code": vcode},
        )
        self._capture_session(data)
        return data

    def login_by_account(self, account: str, password: str) -> Any:
        md5_pass = hashlib.md5(password.encode("utf-8")).hexdigest()
        data = self._post(
            "/v6/account/login",
            form={
                "login": account,
                "password": password,
                "md5_pass": md5_pass,
                "md5_password": md5_pass,
            },
        )
        self._capture_session(data)
        return data

    def _capture_session(self, data: Any) -> None:
        """从登录响应里取回 SESSID 等凭据。"""
        if not isinstance(data, dict):
            return
        cookie_parts = []
        for key in ("SESSID", "uid", "username", "token", "displayVersion"):
            value = data.get(key)
            if value not in (None, "", 0):
                cookie_parts.append(f"{key}={value}")
        if cookie_parts:
            merged = sanitize_cookie(self.cookie + "; " + "; ".join(cookie_parts))
            self.cookie = merged

    def login_by_cookie(self, cookie: str) -> dict[str, Any]:
        """导入浏览器 Cookie 登录，并校验账号信息。"""
        self.set_cookie(cookie)
        if "SESSID=" not in self.cookie:
            raise CoolapkError("Cookie 里没有 SESSID，登录态无效")
        info = self.check_login_info()
        if not isinstance(info, dict) or not info.get("uid"):
            raise CoolapkError("酷安返回的账号信息为空，Cookie 可能已过期")
        return info

    def check_login_info(self) -> Any:
        return self._get("/v6/account/checkLoginInfo")

    # ---------- 读取 ----------

    def index_v8(self, page: int = 1) -> Any:
        """首页推荐流。"""
        return self._get(
            "/v6/main/indexV8",
            [
                ("page", str(page)),
                ("firstLaunch", "0"),
                ("installTime", "0"),
                ("firstItem", ""),
                ("lastItem", ""),
                ("ids", ""),
            ],
        )

    def page_data_list(self, url: str, title: str = "", page: int = 1, **extra) -> Any:
        """官方 V8 页面数据入口（#/feed/statList 等）。"""
        query = [("url", url), ("title", title), ("page", str(page))]
        for key, value in extra.items():
            query.append((key, str(value)))
        return self._get("/v6/page/dataList", query)

    def hot_feeds(self, page: int = 1) -> Any:
        """热门（7 天点赞榜），附官方降级路径。"""
        return self._page_list_with_fallback(
            [
                ("#/feed/statList?statType=7days&sortField=likenum", "热门"),
                ("#/feed/statHotList?period=24h", ""),
            ],
            page,
        )

    def rank_feeds(self, page: int = 1) -> Any:
        """总榜。"""
        return self._page_list_with_fallback([("#/feed/statList?statType=total", "总榜")], page)

    def latest_feeds(self, page: int = 1) -> Any:
        """快讯（最新动态），附官方降级路径。"""
        return self._page_list_with_fallback(
            [
                ("V11_HOME_TAB_NEWS", "快讯"),
                ("#/feed/digestList?type=1", "快讯"),
                ("#/feed/newestList", ""),
            ],
            page,
        )

    def digest_feeds(self, page: int = 1) -> Any:
        return self._page_list_with_fallback([("#/feed/digest", "摘要")], page)

    def cool_picture_rank(self, page: int = 1) -> Any:
        return self._page_list_with_fallback([("#/feed/picture", "酷图")], page)

    def secondhand_feeds(self, page: int = 1) -> Any:
        return self._page_list_with_fallback([("#/feed/secondhand", "二手")], page)

    def _page_list_with_fallback(self, targets: list[tuple[str, str]], page: int) -> Any:
        """按顺序尝试多个 V8 页面入口，返回第一个有结果的。"""
        last_error: CoolapkError | None = None
        for url, title in targets:
            try:
                payload = self.page_data_list(url, title, page)
            except CoolapkError as error:
                last_error = error
                continue
            if isinstance(payload, list) and payload:
                return payload
            if isinstance(payload, dict) and payload.get("data"):
                return payload["data"]
        if last_error is not None:
            raise last_error
        return []

    def feed_detail(self, feed_id: str) -> Any:
        """动态详情。

        酷安对游客身份封锁了 /v6/feed/detail（返回验证码或「应用未授权」），
        登录后正常。游客态降级到 hotReplyList 拿评论，
        再用 /v6/feed/replyDetail 之类不需要正文权限的端点补充。
        """
        try:
            return self._get_with_fallback("/v6/feed/detail", [("id", str(feed_id))])
        except CoolapkError as error:
            if not (error.is_captcha or "未授权" in str(error)):
                raise
            return self._guest_feed_detail(feed_id)

    def _guest_feed_detail(self, feed_id: str) -> Any:
        """游客态的详情兜底：拼出可用的动态信息。"""
        detail: dict[str, Any] = {
            "id": feed_id,
            "url": f"/feed/{feed_id}",
            "guestOnly": True,
            "note": "酷安对游客身份封锁了动态详情接口，此结果来自公开列表的降级拼装",
        }
        # 热门评论端点游客可用，顺带证明该动态存在并给出互动数据。
        try:
            hot = self._get(
                "/v6/feed/hotReplyList",
                [("id", str(feed_id)), ("page", "1"), ("discussMode", "1")],
            )
            replies = hot if isinstance(hot, list) else []
            detail["replyCount"] = len(replies)
            detail["hotReplies"] = [
                {
                    "id": r.get("id"),
                    "username": r.get("username"),
                    "message": str(r.get("message") or "")[:200],
                }
                for r in replies[:5]
                if isinstance(r, dict)
            ]
        except CoolapkError:
            pass
        return detail

    def feed_replies(
        self,
        feed_id: str,
        page: int = 1,
        list_type: str = "lastupdate_desc",
        first_item: str = "",
        last_item: str = "",
    ) -> Any:
        """评论列表。

        官方 APK 的 replyList 会带 discussMode / feedType / blockStatus /
        fromFeedAuthor 四个固定参数。酷安对游客的 replyList 与 feed/detail
        会要求滑块验证，因此这两个端点被风控时降级到 hotReplyList
        （热门评论，同样是官方端点，游客态可用）。
        """
        query = [
            ("id", str(feed_id)),
            ("listType", list_type),
            ("page", str(page)),
            ("discussMode", "1"),
            ("feedType", "feed"),
            ("blockStatus", "0"),
            ("fromFeedAuthor", "0"),
        ]
        if first_item:
            query.append(("firstItem", first_item))
        if last_item:
            query.append(("lastItem", last_item))
        try:
            return self._get_with_fallback("/v6/feed/replyList", query)
        except CoolapkError as error:
            if not error.is_captcha:
                raise
            return self._get(
                "/v6/feed/hotReplyList",
                [("id", str(feed_id)), ("page", str(page)), ("discussMode", "1")],
            )

    def hot_replies(self, feed_id: str, page: int = 1) -> Any:
        """热门评论（游客态可用）。"""
        return self._get(
            "/v6/feed/hotReplyList",
            [("id", str(feed_id)), ("page", str(page)), ("discussMode", "1")],
        )

    def sub_replies(self, feed_id: str, reply_id: str, page: int = 1) -> Any:
        return self._get(
            "/v6/feed/replyListBySub",
            [("id", str(feed_id)), ("rid", str(reply_id)), ("page", str(page))],
        )

    def hot_replies(self, feed_id: str, page: int = 1) -> Any:
        return self._get("/v6/feed/hotReplyList", [("id", str(feed_id)), ("page", str(page))])

    def search(self, query_text: str, search_type: str = "all", page: int = 1) -> Any:
        return self._get(
            "/v6/search",
            [
                ("q", query_text),
                ("type", search_type),
                ("page", str(page)),
                ("sortType", "hot"),
                ("searchType", search_type),
            ],
        )

    def user_profile(self, uid: str) -> Any:
        return self._get("/v6/user/profile", [("uid", str(uid))])

    def user_space(self, uid: str) -> Any:
        return self._get("/v6/user/space", [("uid", str(uid))])

    def user_feeds(self, uid: str, page: int = 1, feed_type: str = "") -> Any:
        query = [("uid", str(uid)), ("page", str(page))]
        if feed_type:
            query.append(("feedType", feed_type))
        return self._get("/v6/user/feedList", query)

    def user_follow_list(self, uid: str, page: int = 1) -> Any:
        return self._get("/v6/user/followList", [("uid", str(uid)), ("page", str(page))])

    def topic_detail(self, tag: str) -> Any:
        return self._get("/v6/topic/newTagDetail", [("tag", tag)])

    def topic_feed_list(self, tag: str, page: int = 1, list_type: str = "lastupdate_desc") -> Any:
        return self._get(
            "/v6/topic/tagFeedList",
            [("tag", tag), ("page", str(page)), ("listType", list_type)],
        )

    def topic_list(self, page: int = 1) -> Any:
        return self.page_data_list("#/topic/tagList", "话题", page)

    def notifications(self, notify_type: str = "list", page: int = 1) -> Any:
        return self._get("/v6/notification/list", [("type", notify_type), ("page", str(page))])

    def favorites(self, fav_type: str = "feed", page: int = 1) -> Any:
        return self._get("/v6/user/favList", [("favType", fav_type), ("page", str(page))])

    def following_feeds(self, page: int = 1) -> Any:
        return self._get("/v6/feed/followFeedList", [("page", str(page))])

    def private_messages(self, page: int = 1) -> Any:
        return self._get("/v6/message/list", [("page", str(page))])

    # ---------- 写操作 ----------

    def like_feed(self, feed_id: str, ddid: str | None = None) -> Any:
        return self._post(
            "/v6/feed/like",
            query=[("id", str(feed_id)), ("detail", "0")],
            form={"trace": ""},
            ddid=ddid,
        )

    def unlike_feed(self, feed_id: str) -> Any:
        return self._post(
            "/v6/feed/unlike",
            query=[("id", str(feed_id)), ("detail", "0")],
            form={"trace": ""},
        )

    def like_reply(self, reply_id: str, ddid: str | None = None) -> Any:
        return self._post(
            "/v6/feed/likeReply",
            query=[("id", str(reply_id)), ("detail", "0")],
            form={"trace": ""},
            ddid=ddid,
        )

    def reply_feed(
        self,
        feed_id: str,
        message: str,
        reply_id: str | None = None,
        pic: str | None = None,
        post_token: str | None = None,
        ddid: str | None = None,
        image_paths: list[str] | None = None,
    ) -> Any:
        """评论动态；带 reply_id 时是楼中楼回复。"""
        if reply_id:
            target_id, reply_type = str(reply_id), "reply"
        else:
            target_id, reply_type = str(feed_id), "feed"

        uploaded: list[str] = []
        for path in image_paths or []:
            from .upload import upload_image_file

            uploaded.append(upload_image_file(self, path))
        if uploaded:
            pic = ",".join([p for p in (pic or "").split(",") if p] + uploaded)

        form = {"message": message}
        if pic:
            form["pic"] = pic
        if post_token:
            form["_v2_post_token"] = post_token
        return self._post(
            "/v6/feed/reply",
            query=[("id", target_id), ("type", reply_type)],
            form=form,
            ddid=ddid,
        )

    def create_feed(
        self,
        message: str,
        pic: str | None = None,
        post_token: str | None = None,
        visible_status: int = 1,
        forward_id: str | None = None,
        feed_type: str = "feed",
        fid: str = "",
        ddid: str | None = None,
        extra: dict[str, str] | None = None,
        image_paths: list[str] | None = None,
    ) -> Any:
        """发布动态。

        message 与 pic 至少给一项；pic 是逗号分隔的图片地址。
        visible_status: 1 公开 / -1 仅自己。
        image_paths 给本机图片路径时自动上传后填入 pic。
        """
        if not message.strip() and not (pic or "").strip() and not image_paths:
            raise CoolapkError("动态正文与图片至少要有一项")

        uploaded: list[str] = []
        for path in image_paths or []:
            from .upload import upload_image_file

            uploaded.append(upload_image_file(self, path))
        if uploaded:
            pic = ",".join([p for p in (pic or "").split(",") if p] + uploaded)

        form: dict[str, str] = {key: value for key, value in CREATE_FEED_FIELDS}
        form["message"] = message
        form["pic"] = pic or ""
        form["type"] = feed_type
        form["fid"] = fid
        form["publish_status"] = "1" if visible_status == -1 else "0"
        if forward_id:
            form["forwardid"] = str(forward_id)
        if post_token:
            form["_v2_post_token"] = post_token
        if extra:
            form.update({key: str(value) for key, value in extra.items()})
        return self._post("/v6/feed/createFeed", form=form, ddid=ddid)

    def forward_feed(
        self, feed_id: str, message: str = "", pic: str | None = None, ddid: str | None = None
    ) -> Any:
        return self.create_feed(message, pic=pic, forward_id=feed_id, ddid=ddid)

    def follow_user(self, uid: str) -> Any:
        return self._post("/v6/user/follow", query=[("uid", str(uid))], form={})

    def unfollow_user(self, uid: str) -> Any:
        return self._get("/v6/user/unfollow", [("uid", str(uid))])

    def follow_topic(self, tag: str) -> Any:
        tag = tag.strip().strip("#")
        return self._get("/v6/feed/followTag", [("tag", tag)])

    def unfollow_topic(self, tag: str) -> Any:
        tag = tag.strip().strip("#")
        return self._get("/v6/feed/unFollowTag", [("tag", tag)])

    def send_message(self, uid: str, message: str) -> Any:
        return self._post(
            "/v6/message/send",
            query=[("uid", str(uid))],
            form={"message": message},
        )

    def delete_feed(self, feed_id: str) -> Any:
        """删除自己发布的动态。

        必须 POST + id 放 URL query + X-Requested-With: XMLHttpRequest，
        GET 会返回 status=-1「请求方式错误」。
        """
        return self._post("/v6/feed/deleteFeed", query=[("id", str(feed_id))], form={})

    def delete_reply(self, reply_id: str) -> Any:
        """删除自己发表的评论。"""
        return self._post("/v6/feed/deleteReply", query=[("id", str(reply_id))], form={})
