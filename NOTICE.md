# 声明与免责声明

## 项目性质

本项目是**酷安官方接口的非官方客户端**，与酷安官方及深圳酷安网络科技有限公司
无隶属、授权或合作关系。酷安名称、Logo 和相关商标归其权利人所有。

本项目基于对 [coolapk-desktop](https://github.com/coolapk-desktop/coolapk-desktop)
（社区维护的 Rust 桌面客户端）的分析实现，端点、请求头与签名算法来自对它的逆向研究。

## 使用者责任

- 所有请求均以**使用者自己的账号身份**发起。
- 账号封禁、风控、封号等风险由使用者自行承担。
- 解锁 Bootloader、刷机、修改系统分区等操作可能导致设备变砖，请自行评估风险。
- 请遵守酷安的服务条款与相关法律法规。

## 凭据处理

- 登录 Cookie 只保存在本机 `%USERPROFILE%\.coolapk-cli\state.json`（可用环境变量
  `COOLAPK_CLI_HOME` 改位置），项目不会把凭据发送到任何第三方服务。
- `.gitignore` 已排除所有状态与凭据文件，请勿把 `state.json` 提交到版本库。
- 请不要把包含真实 Cookie 的文本或截图发到 Issue、聊天群或公开仓库。

## 第三方项目

| 项目 | 许可 | 用途 |
| --- | --- | --- |
| [coolapk-desktop](https://github.com/coolapk-desktop/coolapk-desktop) | MIT | 接口与签名算法的参考实现 |
| [kongwufang/szlm_res](https://github.com/kongwufang/szlm_res) | MIT | 数盟 DUID 协议参考 |
| [bcrypt](https://github.com/pyca/bcrypt) | Apache-2.0 | Token V3 签名 |

## 免责声明

本软件按「现状」提供，不对适销性、特定用途适用性或无侵权做任何明示或暗示的保证。
因使用本软件造成的任何直接或间接损失，作者不承担责任。
