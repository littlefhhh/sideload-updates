# sideload-updates

把 GitHub Releases 自动变成 **SideStore / AltStore 可订阅的应用源**，用来接收开源 App 的版本更新。

原理：脚本读取 `config.json` 里配置的仓库 → 抓取最新 Release 的 `.ipa` → 生成标准的 `source.json`。
手机端把 `source.json` 加为源后，SideStore 刷新时会比对版本号，有新版本就在「更新」页出红点并推送通知，点一下就能升级。

## 当前部署（已上线）

| 项目 | 值 |
|---|---|
| 仓库 | https://github.com/littlefhhh/sideload-updates |
| 订阅地址 | `https://littlefhhh.github.io/sideload-updates/source.json` |
| 落地页 | https://littlefhhh.github.io/sideload-updates/ |
| 当前收录 | Anx Reader 1.14.0（`com.anxcye.anxReader`） |
| 自动检查 | 每天北京时间 09:00，或每次 push |

手机端：SideStore → `Sources` → `+` → 粘贴订阅地址 → 完成后在「更新」页看红点。

> 推送用仓库里的**部署密钥**（`git@github.com:littlefhhh/sideload-updates.git`），
> 因为 OAuth 令牌无权推送 `.github/workflows/` 下的文件。私钥在本机
> `/Users/liguofang/WorkBuddy/2026-10-31-23-02-14/.tools/deploy_key`，
> 不需要时到仓库 `Settings → Deploy keys` 删除即可。

---

## 三步上线

本目录已经是一个可直接推送的 git 仓库（首次提交已完成），最省事的路径：

```bash
# 1) 先在 github.com/new 建一个空仓库（Public，不要勾选 README）
# 2) 回到这里执行，把 <用户名>/<仓库名> 换成你自己的
./deploy.sh <用户名>/sideload-updates
# 3) 按脚本结尾打印的提示，在网页上开 Pages、跑一次 Actions
```

`deploy.sh` 会自动把订阅地址改成真实的 `<用户名>.github.io` 域名、重新抓取上游版本、并推送。

手动版等价操作：

1. **建仓库**：在 GitHub 新建一个仓库，把本目录内容推上去。
2. **开 Pages**：仓库 `Settings → Pages → Build and deployment`，Source 选 `Deploy from a branch`，分支 `main`、目录 `/docs`，保存。
3. **跑一次**：`Actions → 更新应用源 → Run workflow`。约 1 分钟后打开
   `https://<用户名>.github.io/<仓库名>/` 就能看到订阅地址。

订阅地址固定为：

```
https://<用户名>.github.io/<仓库名>/source.json
```

## 手机端接收更新

1. SideStore / AltStore → `Sources` → 右上角 `+` → 粘贴上面的地址。
2. 系统设置里给 SideStore 打开**通知**权限，`Updates` 页才会弹出"有新版本"。
3. 之后每次刷新（SideStore 是手机端自动/下拉刷新，AltStore 需要 AltServer 同 Wi-Fi）都会比对版本号。

> 用你自己的付费开发者账号登录 SideStore，证书约 1 年，更新时不会因为 7 天过期被打断。

## 添加新的 App

在 `config.json` 的 `apps` 数组里加一项即可：

| 字段 | 必填 | 说明 |
|---|---|---|
| `repo` | 是 | `owner/repo`，必须是**发布里带 `.ipa` 附件**的仓库 |
| `bundleIdentifier` | 是 | App 的 Bundle ID，写错会导致更新识别失败 |
| `name` / `subtitle` / `developerName` | 否 | 展示用文字 |
| `versionRegex` | 否 | tag 里取版本号的正则，如 `_([0-9.]+)$` 从 `v1.15.11_4.0.1` 取 `4.0.1` |
| `assetPattern` | 否 | 多个 IPA 时按文件名筛选，如 `iOS\.ipa$` 排除 tvOS |
| `minOSVersion` | 否 | 默认 `14.0` |
| `inspect` | 否 | `true` 时下载 IPA 读真实 `CFBundleShortVersionString`（慢，仅本地调试用） |

**版本号必须和 App 内部的版本号一致**，否则 SideStore 会认为"没有新版本"。不确定时先跑一次：

```bash
python3 gen_source.py --repo owner/repo --inspect
```

## 本地运行

```bash
python3 gen_source.py --base-url https://<用户名>.github.io/<仓库名>
```

只用标准库，无需 `pip install`。设 `GITHUB_TOKEN` 环境变量可把 API 限流从 60 次/小时提到 5000 次/小时。

> 若本机开了代理但没启动，记得先 `unset http_proxy https_proxy all_proxy`，否则请求会直接失败。

## 已知限制

- **只有源码、没有 IPA 附件的仓库**（例如 uYouPlus 现在只发 Actions artifact）无法直装，脚本会打印警告并跳过。这类需要自己编译或改用发布 IPA 的 fork。
- 每日定时任务是 UTC 01:00，GitHub 免费额度下定时任务偶尔会延迟几十分钟，属正常。
- 源只负责"告知 + 给下载链接"，签名仍由 SideStore 用你的账号完成，脚本不接触任何证书。

## 不想搭这套怎么办

如果只关注一两个 App，其实不用自建源：

- GitHub 仓库页 `Watch → Custom → Releases`，新版直接发邮件；
- 或订阅 RSS：`https://github.com/owner/repo/releases.atom`，丢进 NetNewsWire / Reeder 即可。
