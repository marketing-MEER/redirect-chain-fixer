"""Command line entry point: `redirect-chain-fixer --map REDIRECTS.csv` or `redirect-chain-fixer --urls URLS.txt`."""
from pathlib import Path

import click
import pandas as pd

from . import __version__, core
from .benchmark import STATS
from .report import Report, write_excel


@click.command()
@click.option("--map", "map_file", type=click.Path(exists=True), default=None,
              help="Redirect map CSV (source, target[, status]). Checked offline.")
@click.option("--urls", "urls_file", type=click.Path(exists=True), default=None,
              help="URL list (.txt one per line, or a CSV with a URL/Address column). Requested live.")
@click.option("--delay", default=0.5, show_default=True, help="Seconds between requests in live mode (min 0.5).")
@click.option("-o", "--output", default="redirect_chains", show_default=True,
              help="Report name; writes <name>.html, .xlsx, .htaccess and .nginx.conf")
@click.version_option(__version__)
def main(map_file, urls_file, delay, output):
    """Find redirect chains and loops and write the direct redirect rules that replace them.

    Built by Meer Hamza - linkedin.com/in/meerhamza-seo
    """
    if not map_file and not urls_file:
        raise click.UsageError("Give --map FILE (offline) or --urls FILE (live), or both.")
    out = Path(output)
    report = Report(title="Redirect chain report", subtitle="", tool="redirect-chain-fixer")
    cards, sources, rules_parts, summaries = [], [], [], []

    flat = live = None
    if map_file:
        m = core.load_map(map_file)
        flat = core.flatten(m)
        sources.append(f"{Path(map_file).name}: {len(m):,} rules")
        bad = flat[flat["issue"] != ""]
        cards += [("Rules in map", len(m)),
                  ("Chains", int(flat["issue"].str.contains("chain").sum()), "warn"),
                  ("Loops", int(flat["issue"].str.contains("loop|itself").sum()), "bad")]
        rules_parts.append(core.direct_rules(flat, "source", "final_target"))
        summaries.append(("Map", core.summary(flat), bad))
    if urls_file:
        urls = core.load_urls(urls_file)
        click.echo(f"Tracing {len(urls)} URLs (about {len(urls) * max(delay, 0.5):.0f}s or more)...")
        live = core.trace_all(urls, delay=delay,
                              progress=lambda i, n: click.echo(f"  {i}/{n}") if i % 25 == 0 else None)
        sources.append(f"{Path(urls_file).name}: {len(urls):,} URLs")
        redirected = live[live["redirects"] > 0]
        cards += [("URLs traced", len(live)), ("Redirecting", len(redirected)),
                  ("Chains (live)", int(live["issue"].str.contains("chain").sum()), "warn"),
                  ("Broken ends", int(live["issue"].str.contains("ends in|loop").sum()), "bad"),
                  ("Avg redirect time", f"{int(redirected['redirect_ms'].mean()) if len(redirected) else 0} ms")]
        rules_parts.append(core.direct_rules(live, "url", "final_url"))
        summaries.append(("Live", core.summary(live), live[live["issue"] != ""]))

    rules = pd.concat(rules_parts, ignore_index=True)
    rules = rules[~rules["source"].map(core._path).duplicated()].reset_index(drop=True)  # map rules win
    cards.append(("Direct rules written", len(rules), "good"))
    report.subtitle = " · ".join(sources)
    report.add_cards(cards)
    report.add_benchmark(STATS[0], how_used="Every redirect hop is another request before the page starts to "
                         "load, and NP Digital's ranking score drops from 100 at 1 second to 92 at 2 seconds. "
                         "In live mode the time spent on redirect hops is measured per URL.")
    report.add_benchmark(STATS[1], how_used="Automated checks find many more small technical errors than manual "
                         "reviews, and the insight says 'automate fixes where possible'. So the tool doesn't stop "
                         "at a list: it writes the replacement rules for Apache and nginx.")
    report.add_table("Direct redirect rules", rules, sheet="Direct rules",
                     note=f"Also saved as {out.with_suffix('.htaccess').name} and "
                          f"{out.with_suffix('.nginx.conf').name}. Review before going live.")
    for label, summ, bad in summaries:
        report.add_table(f"{label}: issues", summ, sheet=f"{label} issues")
        report.add_table(f"{label}: rules and URLs to fix", bad, sheet=f"{label} to fix")
    if flat is not None:
        report.add_table("Map: all rules", flat, sheet="Map all")
    if live is not None:
        report.add_table("Live: all URLs", live, sheet="Live all")

    html_path = report.save_html(out.with_suffix(".html"))
    xlsx_path = write_excel(report.sheets, out.with_suffix(".xlsx"))
    out.with_suffix(".htaccess").write_text(core.htaccess(rules), encoding="utf-8")
    out.with_suffix(".nginx.conf").write_text(core.nginx(rules), encoding="utf-8")
    click.secho(f"Report: {html_path}\nData:   {xlsx_path}\nRules:  {out.with_suffix('.htaccess')}, "
                f"{out.with_suffix('.nginx.conf')}", fg="green", bold=True)
    for label, summ, _ in summaries:
        if not summ.empty:
            click.echo(f"{label}:\n" + summ.to_string(index=False))


if __name__ == "__main__":
    main()
