#!/usr/bin/env python3
"""
把 GitHub Releases 变成 SideStore / AltStore 可订阅的应用源（source.json）。

用法:
    python3 gen_source.py                 # 生成 docs/source.json 与 docs/index.html
    python3 gen_source.py --inspect       # 额外下载 IPA 读真实版本号（慢，建议只在本地跑）
    python3 gen_source.py --repo a/b      # 临时只处理某个仓库，便于调试

环境变量:
    GITHUB_TOKEN   可选，避免 60 次/小时的匿名限流
"""

import argparse
import html
import json
import os
import plistlib
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

API = "https://api.github.com"
UA = "sideload-updates/1.0"


def log(msg):
    print(msg, file=sys.stderr)


def gh_get(url):
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.load(resp)


def normalize_version(tag, pattern=None):
    """v2.1.0 / 2.1.0-beta / release-2.1.0 -> 2.1.0"""
    raw = (tag or "").strip()
    if pattern:
        m = re.search(pattern, raw)
        if m:
            return m.group(1) if m.groups() else m.group(0)
    m = re.search(r"\d+(?:\.\d+){0,3}", raw)
    return m.group(0) if m else raw.lstrip("vV") or "1.0"


def pick_ipa_asset(assets, pattern=None):
    """挑出 .ipa 资源。pattern 为正则时优先匹配文件名。"""
    ipas = [a for a in assets if a.get("name", "").lower().endswith(".ipa")]
    if not ipas:
        return None
    if pattern:
        hit = [a for a in ipas if re.search(pattern, a["name"])]
        if hit:
            return hit[0]
    return ipas[0]


def inspect_ipa(url):
    """下载 IPA 读 Info.plist，返回 (CFBundleShortVersionString, CFBundleVersion)。"""
    with tempfile.NamedTemporaryFile(suffix=".ipa", delete=False) as tmp:
        path = tmp.name
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp, open(path, "wb") as out:
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                out.write(chunk)
        with zipfile.ZipFile(path) as zf:
            plist_names = [
                n for n in zf.namelist()
                if re.match(r"^Payload/[^/]+\.app/Info\.plist$", n)
            ]
            if not plist_names:
                return None, None
            with zf.open(plist_names[0]) as fp:
                info = plistlib.load(fp)
        return info.get("CFBundleShortVersionString"), info.get("CFBundleVersion")
    finally:
        if os.path.exists(path):
            os.remove(path)


def build_app(entry, api_release=None):
    repo = entry["repo"]
    release = api_release or gh_get(f"{API}/repos/{repo}/releases/latest")
    tag = release.get("tag_name", "")
    asset = pick_ipa_asset(release.get("assets", []), entry.get("assetPattern"))
    if not asset:
        log(f"  ! {repo} 的 release {tag} 里没有 .ipa，跳过（只有源码的仓库无法直装）")
        return None

    version = entry.get("versionOverride") or normalize_version(tag, entry.get("versionRegex"))
    build = None
    if entry.get("inspect"):
        try:
            short, build = inspect_ipa(asset["browser_download_url"])
            if short:
                version = short
        except Exception as exc:  # 读不到就用 tag 兜底
            log(f"  ! 读取 {repo} 的 Info.plist 失败：{exc}")

    download_url = entry.get("downloadURL") or asset["browser_download_url"]
    notes = re.sub(r"\n{3,}", "\n\n", (release.get("body") or "").strip())
    if len(notes) > 600:
        notes = notes[:600].rstrip() + " …"

    app = {
        "name": entry.get("name") or repo.split("/")[1],
        "bundleIdentifier": entry["bundleIdentifier"],
        "developerName": entry.get("developerName", repo.split("/")[0]),
        "subtitle": entry.get("subtitle", ""),
        "localizedDescription": entry.get("description") or notes or entry.get("subtitle", ""),
        "iconURL": entry.get("iconURL") or "",
        "tintColor": entry.get("tintColor") or "#2F6FEB",
        "category": entry.get("category", "utilities"),
        "screenshots": entry.get("screenshots", []),
        "versions": [
            {
                "version": version,
                "date": release.get("published_at", ""),
                "localizedDescription": notes,
                "downloadURL": download_url,
                "size": asset.get("size", 0),
                "minOSVersion": entry.get("minOSVersion", "14.0"),
            }
        ],
        # 以下为旧版格式镜像，保证老客户端也能识别
        "version": version,
        "versionDate": release.get("published_at", ""),
        "versionDescription": notes,
        "downloadURL": download_url,
        "size": asset.get("size", 0),
        "minOSVersion": entry.get("minOSVersion", "14.0"),
    }
    if build:
        app["versions"][0]["buildVersion"] = build
    if entry.get("beta"):
        app["beta"] = True

    log(f"  + {app['name']:<22} {version:<12} {asset['size'] / 1048576:.1f} MB")
    return app


def render_index(src, apps, source_url):
    rows = []
    for app in apps:
        v = app["versions"][0]
        rows.append(
            "<tr><td>{}</td><td class='mono'>{}</td><td>{}</td><td class='mono'>{}</td></tr>".format(
                html.escape(app["name"]),
                html.escape(app["bundleIdentifier"]),
                html.escape(v["version"]),
                html.escape(v["date"][:10]),
            )
        )
    alt = "altstore://source?url=" + urllib.parse.quote(source_url, safe="")
    side = "sidestore://source?url=" + urllib.parse.quote(source_url, safe="")
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--b:#e6e6e6;--t:#111;--m:#666;--bg:#fff}}
@media (prefers-color-scheme:dark){{:root{{--b:#333;--t:#eee;--m:#999;--bg:#161616}}}}
body{{margin:0;padding:32px 20px;background:var(--bg);color:var(--t);
font:14px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",sans-serif}}
.wrap{{max-width:720px;margin:0 auto}}
h1{{font-size:19px;font-weight:600;margin:0 0 6px}}
p.sub{{color:var(--m);margin:0 0 24px;font-size:13px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0 24px}}
th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid var(--b)}}
th{{color:var(--m);font-weight:500;font-size:12px}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}}
a.btn{{display:inline-block;margin:6px 8px 0 0;padding:8px 14px;border:1px solid var(--b);
border-radius:9px;color:var(--t);text-decoration:none;font-size:13px}}
a.btn:hover{{border-color:var(--m)}}
code{{font-family:ui-monospace,Menlo,monospace;font-size:12px;word-break:break-all;color:var(--m)}}
</style></head>
<body><div class="wrap">
<h1>{title}</h1>
<p class="sub">{desc}</p>
<p><a class="btn" href="{alt}">添加到 AltStore</a>
<a class="btn" href="{side}">添加到 SideStore</a></p>
<p><code>{source_url}</code></p>
<table><thead><tr><th>应用</th><th>Bundle ID</th><th>版本</th><th>发布日期</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="sub">本页由 gen_source.py 自动生成，每天随 GitHub Releases 更新。</p>
</div></body></html>
""".format(
        title=html.escape(src["name"]),
        desc=html.escape(src.get("description", "")),
        alt=html.escape(alt),
        side=html.escape(side),
        source_url=html.escape(source_url),
        rows="\n".join(rows),
    )


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(here, "config.json"))
    ap.add_argument("--out", default=os.path.join(here, "docs"))
    ap.add_argument("--inspect", action="store_true", help="下载 IPA 读取真实版本号")
    ap.add_argument("--repo", help="只处理指定 owner/repo，用于调试")
    ap.add_argument("--base-url", default=os.environ.get("SOURCE_BASE_URL", ""),
                    help="Pages 根地址，如 https://you.github.io/sideload-updates")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as fp:
        cfg = json.load(fp)

    entries = cfg["apps"]
    if args.repo:
        entries = [e for e in entries if e["repo"] == args.repo]

    apps, failed = [], []
    log("检查上游版本：")
    for entry in entries:
        try:
            built = build_app(dict(entry, inspect=entry.get("inspect", args.inspect)))
            if built:
                apps.append(built)
            else:
                failed.append(entry["repo"])
        except urllib.error.HTTPError as exc:
            log(f"  ! {entry['repo']} 请求失败 {exc.code}（可能是限流或仓库不存在）")
            failed.append(entry["repo"])
        except Exception as exc:
            log(f"  ! {entry['repo']} 出错：{exc}")
            failed.append(entry["repo"])

    if not apps:
        log("\n没有任何可用应用，未覆盖旧文件。")
        return 1

    source = dict(cfg["source"])
    source["apps"] = apps
    source.setdefault("news", [])
    source["featuredApps"] = [a["bundleIdentifier"] for a in apps[:3]]

    os.makedirs(args.out, exist_ok=True)
    out_json = os.path.join(args.out, "source.json")
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump(source, fp, ensure_ascii=False, indent=2)

    base = args.base_url.rstrip("/")
    source_url = f"{base}/source.json" if base else "https://<你的 Pages 域名>/source.json"
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as fp:
        fp.write(render_index(source, apps, source_url))

    log(f"\n已生成 {out_json}")
    log(f"订阅地址：{source_url}")
    if failed:
        log("跳过：" + ", ".join(failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
