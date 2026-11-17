# 酷安客户端（CLI + MCP + DSH Skill）

基于 [coolapk-desktop](https://github.com/coolapk-desktop/coolapk-desktop)（Rust 桌面版）的逆向实现，
用 Python 重写的酷安接口客户端。直接对接酷安官方 `api.coolapk.com`，签名算法与官方客户端一致。

游客态可读公开内容；导入账号 Cookie 后可发布动态、评论、点赞、关注、删除。

## 目录结构

```
coolapk/
├── coolapk/                 # Python 包
│   ├── auth.py              # Token V3 离线签名器
│   ├── auth_blob.b64        # 官方密码表
│   ├── client.py            # API 客户端（读写端点）
│   ├── shuzilm.py           # 数盟 DUID 生成（写接口必需）
│   ├── upload.py            # OSS 图片直传
│   ├── cli.py               # CLI 命令实现
│   └── state.py             # 本地凭据存储
├── mcp_server.py            # MCP stdio 服务（20 个工具）
├── skills/coolapk/SKILL.md  # DeepSeek Harness skill
├── dsh-bundle/              # DSH 插件 bundle（注册 MCP 服务）
├── tools/coolapk.cmd        # Windows 命令行入口
└── docs/                    # 调研报告
```

## 安装

```bash
pip install requests bcrypt
```

Python 3.10+。

## CLI 用法

Windows 用 `tools\coolapk.cmd`（自动探测 PATH 里的 python），
其它平台直接 `python -m coolapk`：

```bash
tools\coolapk.cmd feed --page 1          # 首页推荐
tools\coolapk.cmd hot                    # 热门榜
tools\coolapk.cmd latest                 # 最新动态
tools\coolapk.cmd topic 数码日常 --feeds  # 话题动态
tools\coolapk.cmd search 小米 --type feed
tools\coolapk.cmd detail 75076951        # 动态详情
tools\coolapk.cmd replies 75076951       # 评论列表
tools\coolapk.cmd user 20320255 --feeds  # 用户主页
tools\coolapk.cmd me                     # 当前账号
tools\coolapk.cmd post "正文" --image-path "C:\path\to\a.jpg"
tools\coolapk.cmd comment 75076951 "评论"
tools\coolapk.cmd like 75076951
tools\coolapk.cmd follow 20320255
tools\coolapk.cmd delete 75120568
tools\coolapk.cmd logout
```

Python 不在 PATH 时用环境变量指定：

```powershell
$env:COOLAPK_PY = "C:\Python312\python.exe"
tools\coolapk.cmd hot
```

加 `--json` 输出原始 JSON。

## MCP 用法

`mcp_server.py` 是标准 MCP stdio 服务，不依赖任何第三方 MCP 框架，
直接实现 JSON-RPC 2.0。

```bash
python mcp_server.py
```

暴露 20 个工具：

| 分类 | 工具 |
| --- | --- |
| 读 | `coolapk_health` `coolapk_me` `coolapk_feed` `coolapk_hot` `coolapk_latest` `coolapk_search` `coolapk_feed_detail` `coolapk_feed_replies` `coolapk_user` `coolapk_user_feeds` `coolapk_topic` |
| 写 | `coolapk_post` `coolapk_comment` `coolapk_like` `coolapk_follow_user` `coolapk_follow_topic` `coolapk_delete_feed` `coolapk_delete_reply` |
| 会话 | `coolapk_login` `coolapk_logout` |

Claude Code / Cursor 等客户端配置：

```json
{
  "mcpServers": {
    "coolapk": {
      "type": "stdio",
      "command": "python",
      "args": ["/absolute/path/mcp_server.py"]
    }
  }
}
```

## DeepSeek Harness 接入

1. 把 `dsh-bundle/` 里的 `command` 和 `args[0]` 改成你的实际绝对路径。
2. 在 DSH 里用「插件 → 添加插件 → 本地目录」装 `dsh-bundle/`，
   或用 `plugin_manager` 的 `install_bundle`。
3. 把 `skills/coolapk/SKILL.md` 放进 `~/.dsh/skills/coolapk/SKILL.md`。

装好后 agent 就能直接调 `mcp__coolapk__*` 工具刷酷安。

## 登录

酷安已下线账号密码与手机号直连登录（403 Unsupported），只能用 Cookie：

1. 浏览器打开 `https://account.coolapk.com/auth/login?type=coolapk` 登录。
2. 打开 `https://www.coolapk.com/` 刷新。
3. F12 → 网络 → 选中 `www.coolapk.com` 主文档 → 标头 → 请求标头 → 复制整串 Cookie。

核心字段：`SESSID`、`uid`、`username`、`token`。

```bash
python -m coolapk login --cookie "SESSID=...; uid=...; token=..."
```

凭据存 `%USERPROFILE%\.coolapk-cli\state.json`（可用环境变量 `COOLAPK_CLI_HOME` 改位置），
只留在本机。

---

# 实现要点

## Token V3 签名

```
index       = ((timestamp + app_code) % 100) * 4 + 0x80
segment     = base64_decode(auth_blob[index : index+0x80])
plain       = "com.coolapk.market&{segment}&{md5(device_code)}&{timestamp}&{app_code}"
password    = md5(base64(plain))
salt22      = base64("{timestamp:x}/{md5(plain)}")[:22]，末字符在标准表左移 5 位
hash        = bcrypt(password, salt=salt22, cost=4)   # 格式 $2y$04$
token       = "v3" + base64(hash)
```

`app_code = 2610162`（酷安 16.6.5），签名用的版本编码必须与 `X-App-Code` 请求头一致。

bcrypt 的 base64 字母表与标准 base64 不同，且是反向位序，
盐和散列都要按 bcrypt 规则解码/编码。

## 请求头

```
X-App-Token: <v3 token>
X-App-Device: <逆序 base64 设备码>
X-App-Id: com.coolapk.market
X-App-Version: 16.6.5
X-App-Code: 2610162
X-App-Supported: 2610162
X-App-Channel: coolapk
X-App-Mode: universal
X-Api-Version: 16
X-Sdk-Int: 36
X-Sdk-Locale: zh-CN
X-Dark-Mode: 0
X-Requested-With: XMLHttpRequest
User-Agent: Dalvik/2.1.0 (Linux; U; Android 16; 23113RKC6C Build/AQ3A.250226.002) (#Build; Redmi; 23113RKC6C; AQ3A.250226.002; 16) +CoolMarket/16.6.5-2610162-universal
```

## 设备码格式

```
{android_id}; ; ; ; Xiaomi; Xiaomi; {model}; {build};
```

Base64 编码后逆序、去掉 `=` 填充。

**登录态必须用数盟 DUID 作首字段**（`device_code_with_duid`）：

```
{DUID}; ; ; ; Xiaomi; Xiaomi; 23113RKC6C; AQ3A.250226.002;
```

首字段不是有效 DUID 时，写接口（createFeed / reply / like）一律返回
`status=-10`「检测到您的网络环境可能异常」。

## 数盟 DUID

写接口需要。协议：合成标识 → JSON → zlib 压缩 → 与固定密钥异或 → POST 采集端点，
响应逆序解码后取 `n_a` 字段。端点 `https://auni.telecome.cn/a/mdna/report`。

`ddid` Cookie 与设备码首字段用**同一个** DUID，保持设备身份一致。

## 图片上传

```
1. POST /v6/upload/ossUploadPrepare   取 STS 凭证与 uploadFileName
2. PUT  直传 OSS（V1 签名，HMAC-SHA1），带 x-oss-callback / x-oss-callback-var
3. pic = uploadImagePrefix + uploadFileName
```

三个必须遵守的点：

| 约束 | 原因 |
| --- | --- |
| pic 地址必须是 `https://` | `http://` 会被酷安替换成 `feed/static/placeholder_check.png` |
| OSS 直传用独立 session（`trust_env=False`） | 复用 API 客户端会把 `Host: api.coolapk.com` 带进 OSS 请求头，返回 `InvalidArgument` |
| `x-oss-callback` 发 base64 串 | 发解码后的 JSON 会报 `The callback configuration is not base64 encoded` |

回调常量必须与官方逐字节一致。

## 端点清单

| 端点 | 方法 | 用途 | 游客可用 |
| --- | --- | --- | --- |
| `/v6/main/indexV8` | GET | 首页推荐 | 是 |
| `/v6/page/dataList` | GET | V8 页面数据（热门/总榜/快讯/酷图/二手） | 是 |
| `/v6/search` | GET | 搜索 | 是 |
| `/v6/topic/newTagDetail` | GET | 话题详情 | 是 |
| `/v6/topic/tagFeedList` | GET | 话题动态 | 是 |
| `/v6/user/profile` | GET | 用户资料 | 是 |
| `/v6/user/feedList` | GET | 用户动态 | 是 |
| `/v6/feed/hotReplyList` | GET | 热门评论 | 是 |
| `/v6/feed/detail` | GET | 动态详情 | **否**（验证码/未授权） |
| `/v6/feed/replyList` | GET | 评论列表 | **否**（验证码） |
| `/v6/upload/ossUploadPrepare` | POST | 取 OSS 凭证 | 需登录 |
| `/v6/feed/createFeed` | POST | 发帖 | 需登录 |
| `/v6/feed/reply` | POST | 评论/楼中楼 | 需登录 |
| `/v6/feed/like` `/unlike` | POST | 点赞 | 需登录 |
| `/v6/feed/deleteFeed` | POST | 删除动态 | 需登录 |
| `/v6/feed/deleteReply` | POST | 删除评论 | 需登录 |
| `/v6/user/follow` `/unfollow` | POST/GET | 关注用户 | 需登录 |
| `/v6/feed/followTag` `/unFollowTag` | GET | 关注话题 | 需登录 |

## 已知限制

- 游客态 `/v6/feed/detail` 与 `/v6/feed/replyList` 被酷安封锁（验证码 / 「应用未授权」）。
  详情已降级为拼装结果，评论已降级到 `hotReplyList`；登录后恢复正常。
- 酷安有垃圾词检测，短词（如「测试」）会被拒：「这些词都用烂啦，说点别的吧」。
- 写接口可能返回 `428 captcha_required`，需用户在酷安完成一次滑块验证后重试。
- 不支持视频动态、实况照片、修改动态类型。
- 搜索的 `type=all` 只返回应用/话题等卡片，需要动态结果时传 `type=feed`。
- 所有操作以当前登录账号身份提交，风控与账号风险由使用者自行承担。

## 参考

- [coolapk-desktop](https://github.com/coolapk-desktop/coolapk-desktop) — Rust 桌面客户端，
  本项目的端点、请求头与签名算法均来自对它的逆向分析。
- 数盟 DUID 协议参考 `kongwufang/szlm_res`（MIT）。

## 许可

MIT，见 [LICENSE](LICENSE)。
