#!/usr/bin/env python3
"""Multi-source Shadowrocket rule aggregator.

Merges several public rule sources into one Shadowrocket config:
  - zhouzhouprogram sr_cnip_ad.conf   (base: CN split + ads, full parse)
  - blackmatrix7 Advertising.list     (REJECT keywords / IP-CIDRs)
  - blackmatrix7 Advertising_Domain   (REJECT domain set)
  - blackmatrix7 Proxy.list           (PROXY)
  - blackmatrix7 China.list           (DIRECT)
  - Loyalsoldier direct/proxy/reject  (YAML payload domain lists)

Dedup: exact dedup, same-policy suffix subsumption, cross-policy
shadowing (emit order REJECT -> DIRECT -> PROXY), IP-CIDR collapse.
Our own header always wins: encrypted-DoH-only DNS, IPv6 off,
Meta domains pinned to PROXY before everything else.

Usage: aggregate.py SRCDIR OUTPUT
SRCDIR must contain: sr.conf, bm7-advertising.list,
bm7-advertising-domain.list, bm7-proxy.list, bm7-china.list,
ls-direct.txt, ls-proxy.txt, ls-reject.txt
Aborts (exit 1, no output written) if any source looks invalid.
"""
import ipaddress
import os
import sys
from datetime import date

RAW_BASE = ("https://raw.githubusercontent.com/packetmeadow/"
            "shadowrocket-rules/main/")
RAW_URL = RAW_BASE + "shadowrocket-doh.conf"
RAW_URL_FULL = RAW_BASE + "shadowrocket-doh-full.conf"

BANNER = [
    "# ============================================================",
    "# 作者自荐：Muse 邀请码 XPD6FV",
    "# 注册 48 小时内填码，双方各得 1B tokens：https://muse.ai/join",
    "# 能订机票酒店、做旅行规划、管邮件日程的私人 AI 助理，日常干活真香",
    "# ============================================================",
]

META_SUFFIXES = [
    "facebook.com", "fbcdn.net", "fbsbx.com", "facebook.net", "fb.com",
    "instagram.com", "cdninstagram.com", "threads.net", "threads.com",
    "messenger.com", "whatsapp.com", "whatsapp.net", "meta.com",
    "oculus.com",
]

DNS_LINE = "dns-server = https://1.1.1.1/dns-query, https://8.8.8.8/dns-query"
POLICIES = ("REJECT", "DIRECT", "PROXY")  # emit order = shadowing order
PRIORITY = {"REJECT": 0, "PROXY": 1, "DIRECT": 2}  # for identical keys


class Pools:
    def __init__(self):
        self.suffix = {p: set() for p in POLICIES}
        self.exact = {p: set() for p in POLICIES}
        self.keyword = {p: set() for p in POLICIES}
        self.ip = {p: [] for p in POLICIES}
        self.dropped_type = 0

    def add(self, typ, value, policy):
        value = value.strip().lower()
        if not value or policy not in POLICIES:
            return
        if typ == "DOMAIN-SUFFIX":
            self.suffix[policy].add(value.rstrip("."))
        elif typ == "DOMAIN":
            self.exact[policy].add(value.rstrip("."))
        elif typ == "DOMAIN-KEYWORD":
            self.keyword[policy].add(value)
        elif typ in ("IP-CIDR", "IP-CIDR6"):
            try:
                self.ip[policy].append(ipaddress.ip_network(value, strict=False))
            except ValueError:
                self.dropped_type += 1
        else:
            self.dropped_type += 1


def parents(domain):
    parts = domain.split(".")
    for i in range(1, len(parts)):
        yield ".".join(parts[i:])


def covered(domain, suffix_set, include_self=True):
    if include_self and domain in suffix_set:
        return True
    return any(p in suffix_set for p in parents(domain))


def load_sr(path, pools, raw_url=RAW_URL):
    """Parse the base config; returns (general_lines, tail_sections_text)."""
    text = open(path, encoding="utf-8").read()
    if "[General]" not in text or "[Rule]" not in text:
        raise ValueError("sr.conf invalid")
    lines = text.splitlines()
    general, tail = [], []
    section = None
    for ln in lines:
        if ln.startswith("[") and ln.rstrip().endswith("]"):
            section = ln.strip("[]").strip().lower()
            if section not in ("general", "rule"):
                tail.append(ln)
            continue
        if section == "general":
            if ln.startswith("dns-server ="):
                general.append(DNS_LINE)
                general.append("ipv6 = false")
            elif ln.startswith("update-url ="):
                general.append(f"update-url = {raw_url}")
            elif ln.startswith("ipv6 ="):
                continue
            elif ln.strip():
                general.append(ln)
        elif section == "rule":
            s = ln.strip()
            if not s or s.startswith("#") or s.startswith("//"):
                continue
            parts = [x.strip() for x in s.split(",")]
            if len(parts) < 2:
                continue
            typ, val = parts[0].upper(), parts[1]
            policy = parts[2].upper() if len(parts) > 2 else ""
            if typ in ("FINAL", "GEOIP"):
                continue  # re-emitted by us at the end
            pools.add(typ, val, policy)
        elif section is not None:
            tail.append(ln)
    return general, "\n".join(tail).strip("\n")


def load_bm7(path, policy, pools, domain_set=False):
    n = 0
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        n += 1
        if domain_set:
            pools.add("DOMAIN-SUFFIX", s.lstrip("+."), policy)
            continue
        parts = [x.strip() for x in s.split(",")]
        if len(parts) < 2:
            continue
        pools.add(parts[0].upper(), parts[1], policy)
    return n


def load_loyalsoldier(path, policy, pools):
    n = 0
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s.startswith("- "):
            continue
        v = s[2:].strip().strip("'\"")
        if not v:
            continue
        n += 1
        if v.startswith("+."):
            pools.add("DOMAIN-SUFFIX", v[2:], policy)
        else:
            pools.add("DOMAIN", v, policy)
    return n


def dedup(pools):
    stats = {}
    # Meta pins are emitted separately at the top; drop pool copies.
    for pol in POLICIES:
        pools.suffix[pol] -= set(META_SUFFIXES)
        pools.exact[pol] -= set(META_SUFFIXES)
    # cross-policy identical keys: keep highest priority policy only
    for kind in ("suffix", "exact", "keyword"):
        store = getattr(pools, kind)
        seen = {}
        for pol in sorted(POLICIES, key=lambda p: PRIORITY[p]):
            for v in store[pol]:
                seen.setdefault(v, pol)
        for pol in POLICIES:
            store[pol] = {v for v in store[pol] if seen[v] == pol}
    # same-policy suffix subsumption + shadowing by earlier blocks
    emitted_suffix = set()
    for pol in POLICIES:
        sfx = pools.suffix[pol]
        keep = set()
        for d in sfx:
            if covered(d, sfx, include_self=False):
                stats["subsumed"] = stats.get("subsumed", 0) + 1
                continue
            if covered(d, emitted_suffix):
                stats["shadowed"] = stats.get("shadowed", 0) + 1
                continue
            keep.add(d)
        pools.suffix[pol] = keep
        emitted_suffix |= keep
        ex = pools.exact[pol]
        pools.exact[pol] = {
            d for d in ex if not covered(d, pools.suffix[pol])
            and not covered(d, emitted_suffix - pools.suffix[pol])
        }
    # IP collapse per policy
    for pol in POLICIES:
        nets = pools.ip[pol]
        v4 = [n for n in nets if n.version == 4]
        v6 = [n for n in nets if n.version == 6]
        pools.ip[pol] = (list(ipaddress.collapse_addresses(v4))
                         + list(ipaddress.collapse_addresses(v6)))
    return stats


def emit(pools, general, tail, tier="lite"):
    out = list(BANNER)
    tier_note = ("精选版（默认订阅）：多源聚合 + 去重，体积与拦截平衡"
                 if tier == "lite" else
                 "全量版：精选版 + blackmatrix7 广告域名全集 + Loyalsoldier 直连全集，拦截最全但体积大、更新慢")
    out += [
        "# 多源聚合：zhouzhouprogram + blackmatrix7 + Loyalsoldier，每日自动合并去重",
        f"# {tier_note}",
        "# DNS 仅加密 DoH（经代理送出），所有域名解析加密，国内外均不经本地明文解析",
        "# Meta 系域名钉死 PROXY（在 GEOIP,CN 之前）；本文件不含任何节点信息",
        f"# 同步日期：{date.today().isoformat()}",
        "[General]",
    ]
    out += general
    out += ["", "[Rule]",
            "# --- Meta 系固定走代理（必须在 GEOIP,CN 之前） ---"]
    out += [f"DOMAIN-SUFFIX,{d},PROXY" for d in META_SUFFIXES]
    counts = {}
    for pol in POLICIES:
        out.append(f"# --- {pol} ---")
        for kw in sorted(pools.keyword[pol]):
            out.append(f"DOMAIN-KEYWORD,{kw},{pol}")
        for d in sorted(pools.suffix[pol]):
            out.append(f"DOMAIN-SUFFIX,{d},{pol}")
        for d in sorted(pools.exact[pol]):
            out.append(f"DOMAIN,{d},{pol}")
        for net in pools.ip[pol]:
            typ = "IP-CIDR" if net.version == 4 else "IP-CIDR6"
            out.append(f"{typ},{net},{pol}")
        counts[pol] = (len(pools.keyword[pol]) + len(pools.suffix[pol])
                       + len(pools.exact[pol]) + len(pools.ip[pol]))
    out += ["GEOIP,CN,DIRECT", "FINAL,PROXY"]
    if tail:
        out += ["", tail]
    return "\n".join(out) + "\n", counts


def build(src, tier):
    """tier: 'lite' (default subscription) or 'full' (adds the two huge
    long-tail sets: bm7 Advertising_Domain + Loyalsoldier direct)."""
    need = {
        "sr.conf": 1000, "bm7-advertising.list": 100,
        "bm7-proxy.list": 50, "bm7-china.list": 20,
        "ls-proxy.txt": 1000, "ls-reject.txt": 1000,
    }
    if tier == "full":
        need["bm7-advertising-domain.list"] = 1000
        need["ls-direct.txt"] = 1000
    for name, min_lines in need.items():
        p = os.path.join(src, name)
        if not os.path.exists(p) or sum(1 for _ in open(p, encoding="utf-8")) < min_lines:
            raise ValueError(f"source {name} missing/too small")
    pools = Pools()
    general, tail = load_sr(os.path.join(src, "sr.conf"), pools,
                            raw_url=RAW_URL if tier == "lite" else RAW_URL_FULL)
    load_bm7(os.path.join(src, "bm7-advertising.list"), "REJECT", pools)
    if tier == "full":
        load_bm7(os.path.join(src, "bm7-advertising-domain.list"), "REJECT",
                 pools, domain_set=True)
    load_bm7(os.path.join(src, "bm7-proxy.list"), "PROXY", pools)
    load_bm7(os.path.join(src, "bm7-china.list"), "DIRECT", pools)
    if tier == "full":
        load_loyalsoldier(os.path.join(src, "ls-direct.txt"), "DIRECT", pools)
    load_loyalsoldier(os.path.join(src, "ls-proxy.txt"), "PROXY", pools)
    load_loyalsoldier(os.path.join(src, "ls-reject.txt"), "REJECT", pools)
    stats = dedup(pools)
    text, counts = emit(pools, general, tail, tier)
    total = sum(counts.values())
    print(f"[{tier}] pools: {counts} total-rules={total} "
          f"bytes={len(text.encode())} dedup={stats} "
          f"dropped-types={pools.dropped_type}")
    return text


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    try:
        lite = build(src, "lite")
        full = build(src, "full")
    except ValueError as e:
        print(f"aborting: {e}", file=sys.stderr)
        return 1
    open(os.path.join(outdir, "shadowrocket-doh.conf"), "w",
         encoding="utf-8").write(lite)
    open(os.path.join(outdir, "shadowrocket-doh-full.conf"), "w",
         encoding="utf-8").write(full)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
