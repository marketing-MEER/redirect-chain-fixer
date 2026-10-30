<div align="center">

# 🔀 redirect-chain-fixer

### Find redirect chains and loops, and get the direct redirect rules for Apache and nginx that replace them.

[![tests](https://github.com/marketing-MEER/redirect-chain-fixer/actions/workflows/ci.yml/badge.svg)](https://github.com/marketing-MEER/redirect-chain-fixer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![No API keys](https://img.shields.io/badge/API%20keys-none%20needed-brightgreen)
[![Part of SEO Toolbox](https://img.shields.io/badge/part%20of-SEO%20Toolbox-orange)](https://github.com/marketing-MEER/seo-toolbox)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Meer%20Hamza-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/meerhamza-seo)

[🚀 Quick start](#quick-start) · [⚙️ How it works](#how-it-works) · [📄 Report](#report) · [❓ FAQ](#faq) · [👤 Author](#author)

</div>

---

## 💡 What it does

Every site migration leaves redirects behind, and the next migration redirects the redirects. After a few years `/old-page` goes through three hops before it lands, some rules point at each other, and nobody knows which ones are safe to change.

`redirect-chain-fixer` reads your redirect map (offline) or traces a list of URLs hop by hop (live), finds chains, loops, self-redirects, temporary redirects and dead ends, and writes the **direct** rules as `.htaccess` and nginx config, ready to review and paste.

- ✅ Map mode: no network, works on any CMS or plugin export (source, target, status)
- ✅ Live mode: every hop with its status code and the time spent on redirects
- ✅ Flags chains, loops, self-redirects, 302/307 in the path, https to http, redirects that end in 404
- ✅ Writes `source -> final target` rules for Apache (`.htaccess`) and nginx
- ✅ Free, MIT licensed, no API keys.

## 📊 Why this matters

> **How Page Load Time Impacts SEO and Conversions** · NP Digital, February 2025 (Ubersuggest, NP Digital, Crazy Egg and 210 marketers)
> - Sites loading in 1 second average a 2.3% conversion rate and score 100 in organic rankings.
> - At 2 seconds, the ranking score drops to 92 and conversion rate to 2.1%.
> - By 4 seconds, the ranking score drops to 57 and conversions to 1.8%.
>
> **AI Detects 3x More SEO Errors Than Humans** · NP Digital, February 2025 (13 SEOs, 5 sites)
> - AI tools detected 259 SEO errors vs. 83 by human audits.
> - AI identifies more technical and small-scale issues.
>
> Data: [page load time and SEO](https://neilpatel.com/marketing-stats/page-speed-seo-conversions/) · [AI vs manual SEO audits](https://neilpatel.com/marketing-stats/seo-audit-ai-vs-manual/)

**How redirect-chain-fixer uses this:** every redirect hop is another round trip before the page starts to load, so live mode measures the time spent on hops per URL. And because the audit insight says *"Automate Fixes Where Possible"*, the tool doesn't stop at a list of problems: it writes the replacement rules.

<a id="quick-start"></a>

## 🚀 Quick start

```bash
git clone https://github.com/marketing-MEER/redirect-chain-fixer.git
cd redirect-chain-fixer
pip install -e .
redirect-chain-fixer --map examples/redirects.csv
```

To try live mode without touching a real site, start the demo server in one terminal and trace in another:

```bash
python examples/demo_server.py
redirect-chain-fixer --urls examples/urls.txt
```

This writes **`redirect_chains.html`** (a formatted report you can open, share or print to PDF), **`redirect_chains.xlsx`** (all the data), **`redirect_chains.htaccess`** and **`redirect_chains.nginx.conf`**.

> [!TIP]
> If the `redirect-chain-fixer` command isn't found, use `python -m redirect_chain_fixer`.

## 📥 Input

| Input | Notes |
|---|---|
| `--map FILE` | CSV with a source and a target column (`source`/`from`/`old url` and `target`/`to`/`new url`), optional `status`. Paths or full URLs; on a single-host map `/a` and `https://site.com/a` count as the same URL. Status defaults to 301 |
| `--urls FILE` | `.txt` with one URL per line, or a CSV with a `URL` / `Address` column (e.g. a crawler export of your old URLs or backlinked URLs) |

Use one or both. With both, map rules win when the same source shows up twice.

<a id="how-it-works"></a>

## ⚙️ How it works

1. **Map mode** follows each source through the map until it reaches a URL that is not a source. More than one hop = chain; coming back to a URL already seen = loop; source = target = redirects to itself.
2. **Live mode** requests each URL **without following redirects**, reads the `Location` header and requests the next hop, up to 10 hops, with at least 0.5 s between requests and its own user agent. It records each status code and how long each redirect hop took.
3. **Issues** (general best practice): chain, loop, redirects to itself, temporary redirect (302/307) in the path, https to http, ends in a non-200 status, source listed more than once.
4. **Rules**: for every chain, a direct `source -> final target` rule with 301. Loops get no rule, because there is no live page to point at; you decide where they should go. Sources with a query string are written as comments, because they need rewrite rules.

### Options

| Option | Default | What it does |
|---|---|---|
| `--map` | none | Redirect map CSV, checked offline |
| `--urls` | none | URL list, traced live |
| `--delay` | `0.5` | Seconds between requests in live mode (never below 0.5) |
| `-o`, `--output` | `redirect_chains` | File name for the report (`.html`, `.xlsx`, `.htaccess`, `.nginx.conf`) |

<a id="report"></a>

## 📄 The report

| Section / Excel sheet | Shows |
|---|---|
| Summary cards | Rules in map, chains, loops, URLs traced, redirecting URLs, broken ends, average redirect time, rules written |
| Benchmark panels | The two NP Digital stats with how the tool uses them |
| **Direct rules** | The new `source -> target` rules (also in the `.htaccess` and `.nginx.conf` files) |
| **Map issues** / **Map to fix** | Issue counts and every map rule with a problem: final target, hops, issue, fix and the full path |
| **Live issues** / **Live to fix** | Issue counts and every traced URL with a problem: final URL and status, hops, redirect time, fix and path with status codes |
| **Map all** / **Live all** | Everything |

<details>
<summary>📄 Example: real output from <code>examples/</code> (fictional site)</summary>

Map mode on `examples/redirects.csv` (14 rules):

| issue | count |
|---|---|
| chain | 4 |
| loop | 2 |
| source listed more than once | 2 |
| temporary redirect in path | 1 |
| redirects to itself | 1 |

`redirect_chains.htaccess`:

```apache
Redirect 301 /old-pricing /pricing
Redirect 301 /features/crm /platform
Redirect 301 /product/crm /platform
Redirect 301 /signup-old https://brightcrm.io/signup
```

Live mode on `examples/urls.txt` against the demo server (redirect times are from a local server, so they are tiny):

| url | final status | redirects | issue | path |
|---|---|---|---|---|
| /old-pricing | 200 | 2 | chain (2 hops) | /old-pricing [301] -> /pricing-2025 [301] -> /pricing [200] |
| /features/crm | 200 | 3 | chain (3 hops) | /features/crm [301] -> /product/crm [301] -> /product [301] -> /platform [200] |
| /blog/crm-tips | 200 | 1 | temporary redirect in path | /blog/crm-tips [302] -> /blog/crm-basics [200] |
| /team | 301 | 2 | loop | /team [301] -> /about [301] -> back to /team |
| /webinar-2024 | 404 | 1 | ends in 404 | /webinar-2024 [301] -> /events [404] |

</details>

## 🧰 More free SEO tools

This repo is one tool in the **[SEO Toolbox](https://github.com/marketing-MEER/seo-toolbox)**, a family of free, single-purpose SEO tools. Related:
- [robots-sitemap-validator](https://github.com/marketing-MEER/robots-sitemap-validator): find redirects, 404s and noindex pages listed in your sitemaps
- [competitor-tech-stack-audit](https://github.com/marketing-MEER/competitor-tech-stack-audit): compare the technical setup of competing sites
- [seo-workhorse](https://github.com/marketing-MEER/seo-workhorse): audit, clustering, redirect mapping and GSC quick wins in one CLI

<a id="faq"></a>

## ❓ FAQ

<details><summary><b>Can I paste the rules straight into production?</b></summary>

Review them first. The rules are written in the same order as your map, and with Apache the first matching `Redirect` wins, so put the new rules above the old ones for the same sources (or remove the old ones). Test a few URLs after deploying.
</details>

<details><summary><b>Does it handle regex or wildcard redirects?</b></summary>

No. Map mode works with exact source URLs. For pattern rules, use live mode on a list of real URLs: it sees what the server actually does, whatever the rule looks like.
</details>

<details><summary><b>Is my data sent anywhere?</b></summary>

Map mode makes no network requests. Live mode only requests the URLs in your list and the redirect targets they point to.
</details>

## 🧪 Tests

```bash
python -m unittest discover -s tests -t . -v
```

## 📄 License

[MIT](LICENSE). Free for personal and commercial use. Benchmark figures © their original publishers and quoted with a link to the source.

<a id="author"></a>

## 👤 Author

**Meer Hamza** · SEO Team Lead · Berlin 🇩🇪
10+ years in SEO, AEO and GEO. I build small tools that take the spreadsheet work out of SEO.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/meerhamza-seo)
[![Email](https://img.shields.io/badge/Email-meerhamza5%40gmail.com-D14836?logo=gmail&logoColor=white)](mailto:meerhamza5@gmail.com)

<div align="center">

**If this saved you time, a ⭐ helps other SEOs find it.**

</div>
