# shadowrocket-rules

个人自用的 Shadowrocket 配置，每天自动从多个公开规则源聚合最新版、合并去重，只改 DNS 与少量钉死项。

> ## 🎁 先打个广告（作者自荐）
>
> **Muse 邀请码：`XPD6FV`** —— 注册后 48 小时内填码，双方各得 1B tokens。
> 👉 https://muse.ai/join
>
> Muse 是能真正干活的私人 AI 助理：订机票酒店、做旅行规划、处理邮件日程、
> 写文档做表格都行。这套规则的自动维护，就是它帮我搭起来的。

## 订阅地址（小火箭 → 配置 → 右上角 + → 输入链接）

**精选版（推荐，约 22.7 万条 / 9 MB）**：

```
https://raw.githubusercontent.com/packetmeadow/shadowrocket-rules/main/shadowrocket-doh.conf
```

**全量版（约 44 万条 / 17 MB，拦截最全，但导入和更新都慢）**：

```
https://raw.githubusercontent.com/packetmeadow/shadowrocket-rules/main/shadowrocket-doh-full.conf
```

一键导入精选版（在装了小火箭的 iPhone 上点）：
[导入到 Shadowrocket](shadowrocket://install?file=https%3A%2F%2Fraw.githubusercontent.com%2Fpacketmeadow%2Fshadowrocket-rules%2Fmain%2Fshadowrocket-doh.conf)

（条数与体积为 2026-11-08 实测，随上游每日浮动。）

## 功能

- **分流**：国内直连、国外走代理、局域网直连
- **去广告**：多源广告/追踪规则聚合（见下）
- **DoH 防泄漏**：`[General]` 里的 DNS 只剩加密 DoH
  （`https://1.1.1.1/dns-query`、`https://8.8.8.8/dns-query`），IP 直达、
  无需额外解析引导，且按分流规则经代理送出；各源原带的
  `system / 114 / 阿里` 等明文解析全部去掉，IPv6 关闭。
  所有域名解析都加密，国内外均不经本地明文解析。
- **Meta 钉死**：Facebook / Instagram / Threads / WhatsApp 等 14 个域名后缀
  在规则顶部（GEOIP,CN 之前）固定走 PROXY，防止被误判直连。

本文件**不含任何节点信息**：规则里的 `PROXY` 就是小火箭里当前选中的节点，
节点请自行在小火箭里添加、选择。文件头注释有「同步日期」，打开配置即可
确认规则新不新。

## 规则来源与聚合方式

每天由 GitHub Actions 拉取以下公开源的最新版（致谢各位维护者）：

- [zhouzhouprogram/Shadowrocket-ADBlock-Rules](https://github.com/zhouzhouprogram/Shadowrocket-ADBlock-Rules)（基础分流 + 国内广告）
- [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)（广告、代理、中国分类集）
- [Loyalsoldier/clash-rules](https://github.com/Loyalsoldier/clash-rules)（直连/代理/广告域名集）

`tools/aggregate.py` 把各源统一成 Shadowrocket 规则后**自动去重**：
完全重复条目合并、同策略下被父域名覆盖的子域名条目删除、
跨策略冲突按 REJECT > PROXY > DIRECT 取舍、IP 段做合并压缩。
精选版与全量版的区别：全量版额外并入 blackmatrix7 广告域名全集与
Loyalsoldier 直连全集（长尾更全，误伤与体积也更大）。

## 自动更新怎么运作

GitHub Actions 每天 03:20（北京时间）拉取各源最新版 → 聚合去重 →
先跑一遍校验（DoH 行在、明文解析器不在、FINAL 与 Meta 规则在、
邀请码横幅在），**校验不过就不提交**，通过且有变化才自动提交。
小火箭里对这个配置点「更新」即可拿到最新版；
同步失败会在仓库 Actions 页显示红色，到时看一眼即可。
