#!/usr/bin/env python3
"""Merge upstream Shadowrocket rules with our fixed header + Meta block.

- [General]: DNS lines are rewritten to encrypted DoH only (no system /
  plaintext resolvers), IPv6 off, update-url points at this repo.
- [Rule]: a small Meta block is pinned to PROXY right after the [Rule]
  header, i.e. before GEOIP,CN,DIRECT can misroute it.
Everything else passes through byte-for-byte.

Usage: merge.py UPSTREAM_PATH OUTPUT_PATH
"""
import sys
from datetime import date

RAW_URL = ("https://raw.githubusercontent.com/x950118-maker/"
           "shadowrocket-rules/main/shadowrocket-doh.conf")

BANNER = [
    "# ============================================================\n",
    "# 作者自荐：Muse 邀请码 XPD6FV\n",
    "# 注册 48 小时内填码，双方各得 1B tokens：https://muse.ai/join\n",
    "# 能订机票酒店、做旅行规划、管邮件日程的私人 AI 助理，日常干活真香\n",
    "# ============================================================\n",
]

META_SUFFIXES = [
    "facebook.com", "fbcdn.net", "fbsbx.com", "facebook.net", "fb.com",
    "instagram.com", "cdninstagram.com", "threads.net", "threads.com",
    "messenger.com", "whatsapp.com", "whatsapp.net", "meta.com",
    "oculus.com",
]


def header():
    return BANNER + [
        "# 基于 zhouzhouprogram/Shadowrocket-ADBlock-Rules 的 sr_cnip_ad.conf 修改\n",
        "# 改动仅限 [General]：DNS 全部换成加密 DoH（经代理送出），所有域名解析加密，国内外均不经本地明文解析\n",
        "# [Rule] 顶部另钉死 Meta 系域名走 PROXY（在 GEOIP,CN 之前）；其余规则与原版一致\n",
        "# 本文件不含任何节点信息，节点用小火箭里自选的 PROXY\n",
        f"# 同步日期：{date.today().isoformat()}\n",
    ]


def meta_block():
    lines = ["# --- Meta 系固定走代理（必须在 GEOIP,CN 之前） ---\n"]
    lines += [f"DOMAIN-SUFFIX,{d},PROXY\n" for d in META_SUFFIXES]
    return lines


DNS_LINE = "dns-server = https://1.1.1.1/dns-query, https://8.8.8.8/dns-query\n"


def main() -> int:
    src_path, dst_path = sys.argv[1], sys.argv[2]
    text = open(src_path, encoding="utf-8").read()
    if "[General]" not in text or "[Rule]" not in text:
        print("upstream file looks invalid; refusing to merge", file=sys.stderr)
        return 1
    out = []
    in_general = True
    for ln in text.splitlines(keepends=True):
        if ln.startswith("[Rule]"):
            in_general = False
            out.append(ln)
            out.extend(meta_block())
        elif ln.startswith("# Shadowrocket:"):
            out.extend(header())
        elif ln.startswith("dns-server ="):
            out.append(DNS_LINE)
            out.append("ipv6 = false\n")
        elif ln.startswith("update-url ="):
            out.append(f"update-url = {RAW_URL}\n")
        elif in_general and ln.startswith("ipv6 ="):
            continue
        else:
            out.append(ln)
    open(dst_path, "w", encoding="utf-8").write("".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
