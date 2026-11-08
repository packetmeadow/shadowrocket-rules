# shadowrocket-rules

个人自用的 Shadowrocket 分流配置，规则同步自
[zhouzhouprogram/Shadowrocket-ADBlock-Rules](https://github.com/zhouzhouprogram/Shadowrocket-ADBlock-Rules)
的 `sr_cnip_ad.conf`（国内直连 + 国外代理 + 广告过滤），只改了一处：

- **[General] 的 DNS 全部换成加密 DoH**：`https://1.1.1.1/dns-query` 与
  `https://8.8.8.8/dns-query`，并关闭 IPv6。原版的 `system / 114 / 阿里`
  明文解析已全部去掉——所有域名解析都走加密通道并经代理送出，
  国内外解析都不经本地运营商、不明文泄漏。

本文件**不含任何节点信息**，规则里的 `PROXY` 就是小火箭里当前选中的节点，
节点请自行在小火箭里添加、选择。

## 订阅地址（小火箭 → 配置 → 右上角 + → 输入链接）

```
https://raw.githubusercontent.com/x950118-maker/shadowrocket-rules/main/shadowrocket-doh.conf
```

## 自动更新

GitHub Actions 每天 03:20（北京时间）自动拉取上游最新规则，用
`tools/merge.py` 重新套上上面的 DNS 头，有变化才提交。
小火箭里对这个配置点「更新」即可拿到最新版。
