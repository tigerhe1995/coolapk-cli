---
name: coolapk
description: 刷酷安、查酷安、发酷安。读首页推荐/热门榜/最新动态/话题/搜索/用户主页/评论，发动态/评论/点赞/关注用户与话题/删除内容。需要访问酷安内容或以酷安账号发帖时先读这个。Also use for any task that reads or posts Coolapk (coolapk.com) content.
enabled: true
---

# 酷安刷取与发布

DSH 已接入酷安 MCP 服务（serverName `coolapk`），工具名一律 `mcp__coolapk__*`。
游客态可读公开内容；写操作需要先导入账号 Cookie。

## 1. 先判断是否已登录

调用 `mcp__coolapk__coolapk_health`：

```json
{ "loggedIn": false, "uid": null, "deviceCode": "gsTMwAjL0ADOwMjM…",
  "stateFile": "%USERPROFILE%\\.coolapk-cli\\state.json", "serverVersion": "1.0.0" }
```

- `loggedIn: true` → 直接用所有工具。
- `loggedIn: false` → 读操作照常；写操作（发帖/评论/点赞/关注/删除）必须先登录。

## 2. 工具清单

| 工具 | 参数 | 说明 | 需登录 |
| --- | --- | --- | --- |
| `coolapk_health` | — | 登录状态、uid、凭据位置 | 否 |
| `coolapk_me` | — | 当前账号资料 | 是 |
| `coolapk_feed` | `page` | 首页推荐动态流 | 否 |
| `coolapk_hot` | `page` | 热门榜（7 天点赞榜） | 否 |
| `coolapk_latest` | `page` | 最新动态流 | 否 |
| `coolapk_search` | `q`、`type`、`page` | 搜索，type 取 all/feed/user/topic | 否 |
| `coolapk_feed_detail` | `id` | 动态详情 | 是（游客降级） |
| `coolapk_feed_replies` | `id`、`page`、`listType` | 评论列表 | 是（游客降级） |
| `coolapk_user` | `uid` | 用户资料 | 否 |
| `coolapk_user_feeds` | `uid`、`page` | 用户动态 | 否 |
| `coolapk_topic` | `tag`、`feeds`、`page` | 话题详情/话题动态 | 否 |
| `coolapk_post` | `message`、`image`、`imagePaths`、`private` | 发布动态 | 是 |
| `coolapk_comment` | `feedId`、`message`、`replyId`、`imagePaths` | 评论/楼中楼 | 是 |
| `coolapk_like` | `feedId`、`unlike` | 点赞/取消点赞 | 是 |
| `coolapk_follow_user` | `uid`、`unfollow` | 关注/取关用户 | 是 |
| `coolapk_follow_topic` | `tag`、`unfollow` | 关注/取关话题 | 是 |
| `coolapk_delete_feed` | `feedId` | 删除自己发布的动态 | 是 |
| `coolapk_delete_reply` | `replyId` | 删除自己发表的评论 | 是 |
| `coolapk_login` | `cookie` | 导入 Cookie 登录 | 否 |
| `coolapk_logout` | — | 清除本地凭据 | 否 |

## 3. 典型流程

### 刷首页

```
mcp__coolapk__coolapk_feed { "page": 1 }
```

返回每条含 `id`、`uid`、`username`、`message`（正文，截断到 600 字）、`likeNum`、`replyNum`、`url`。
正文里的话题标签已去掉 HTML 标签，汇报时直接引用文字即可。

### 刷热门榜

```
mcp__coolapk__coolapk_hot { "page": 1 }
```

### 查话题

```
mcp__coolapk__coolapk_topic { "tag": "酷安", "feeds": true }
```

`feeds: true` 返回话题下的动态列表，`false`（默认）返回话题详情。

### 看某人主页

```
mcp__coolapk__coolapk_user { "uid": "20320255" }
mcp__coolapk__coolapk_user_feeds { "uid": "20320255", "page": 1 }
```

二手动态的价格/城市在 `ershou` 字段里。

### 发帖

```
mcp__coolapk__coolapk_post { "message": "正文内容 #话题#" }
mcp__coolapk__coolapk_post { "message": "带图", "imagePaths": ["C:\\图片\\a.jpg"] }
```

- `message` 最多 5000 字，话题直接写 `#话题#`。
- `image` 是已上传好的图片地址；`imagePaths` 是本机图片路径（自动上传，最多 9 张）。
- `private: true` 表示仅自己可见。

### 评论 / 楼中楼

```
mcp__coolapk__coolapk_comment { "feedId": "75076951", "message": "评论内容" }
mcp__coolapk__coolapk_comment { "feedId": "75076951", "message": "回复内容", "replyId": "评论id" }
```

`replyId` 是**被回复评论的 id**（取自 `coolapk_feed_replies` 结果里的 `id`），不是楼中楼目标 id。

### 点赞 / 关注 / 删除

```
mcp__coolapk__coolapk_like { "feedId": "75076951" }
mcp__coolapk__coolapk_like { "feedId": "75076951", "unlike": true }
mcp__coolapk__coolapk_follow_user { "uid": "20320255" }
mcp__coolapk__coolapk_follow_topic { "tag": "数码日常" }
mcp__coolapk__coolapk_delete_feed { "feedId": "75120568" }
```

## 4. 登录（需要写操作时）

浏览器里完成：

1. 打开 `https://account.coolapk.com/auth/login?type=coolapk`，用微信扫码或短信登录。
2. 打开 `https://www.coolapk.com/` 并刷新。
3. F12 → 网络 → 点中 `www.coolapk.com` 主文档 → 标头 → 请求标头 → 复制整串 `Cookie`。
4. 交给 agent 调用 `mcp__coolapk__coolapk_login { "cookie": "<完整 Cookie 串>" }`。

核心字段：`SESSID`、`uid`、`username`、`token`。凭据保存在
`%USERPROFILE%\.coolapk-cli\state.json`，只留在本机。

浏览器已经在同一个浏览器实例登录过时，也可以用 chrome-devtools 直接取：
`document.cookie` 拿不到 `token`（HttpOnly），需要从网络面板的主文档请求头里取完整 Cookie。

## 5. 命令行等价物

CLI 与 MCP 共用同一套实现，仓库根目录下：

```powershell
tools\coolapk.cmd feed --page 1
tools\coolapk.cmd hot
tools\coolapk.cmd topic 酷安 --feeds
tools\coolapk.cmd search 小米 --type feed
tools\coolapk.cmd post "正文" --image-path "C:\path\to\a.jpg"
tools\coolapk.cmd delete 75120568
```

加 `--json` 输出原始 JSON。

## 6. 关键实现约束（改代码时必须遵守）

这几条是踩过坑才定下来的，改动时别回退：

| 约束 | 原因 |
| --- | --- |
| 设备码首字段必须是数盟 DUID | 首字段不是 DUID 时，写接口（createFeed/reply/like）一律返回 `status=-10`「检测到您的网络环境可能异常」 |
| ddid Cookie 与设备码首字段用**同一个** DUID | 两者要保持设备身份一致 |
| 配图地址必须是 `https://` | `http://` 会被酷安替换成 `feed/static/placeholder_check.png` |
| 配图要通过 `uploadImagePrefix + uploadFileName` 拼出 | 官方客户端的取法；OSS 回调体里的 `data.url` 同样是这个值 |
| OSS 直传用独立 session（`trust_env=False`） | 复用 API 客户端会把 `Host: api.coolapk.com` 带进 OSS 请求头，导致 `InvalidArgument` |
| `x-oss-callback` 头必须发 base64 串 | 发解码后的 JSON 会报 `The callback configuration is not base64 encoded` |
| createFeed 表单字段固定 39 个、顺序一致 | 与官方 `build_create_feed_form` 对齐 |
| 删除动态必须 POST + id 放 query | GET 返回 `status=-1`「请求方式错误」 |
| 评论请求要带 `discussMode/feedType/blockStatus/fromFeedAuthor` | 缺参数会被判为异常流量 |

## 7. 已知限制

**游客态被酷安封锁的端点**（登录后自动恢复）：

| 工具 | 游客态行为 |
| --- | --- |
| `coolapk_feed_detail` | `/v6/feed/detail` 返回验证码或「应用未授权」；已降级为拼装结果（id、url、热门评论数与前 5 条热门评论） |
| `coolapk_feed_replies` | `/v6/feed/replyList` 同因被封；已降级到 `/v6/feed/hotReplyList`（热门评论，游客可用） |

**内容审核**：

- 酷安有垃圾词检测，短词（如「测试」）会返回「这些词都用烂啦，说点别的吧」。
- 写接口可能返回 `428 captcha_required`，需用户在酷安完成一次滑块验证后重试。

**能力边界**：

- 账号密码与手机号登录接口已被酷安官方下线（403 Unsupported），只能用 Cookie 登录。
- 不支持视频动态、不支持实况照片、不支持修改动态类型。
- 搜索的 `type=all` 只返回应用/话题等卡片，需要动态结果时显式传 `type=feed`。
