# 📂 Examples

Made-up data for a fictional CRM site (`brightcrm.io`); not a real company.

| File | What |
|---|---|
| `redirects.csv` | A redirect map with typical problems: chains, a loop, a self-redirect, a 302, a duplicate source |
| `urls.txt` | Old URLs to trace live against the demo server |
| `demo_server.py` | A tiny local server that plays back `redirects.csv` on http://127.0.0.1:8001 |

```bash
# offline, map only
redirect-chain-fixer --map examples/redirects.csv

# live, against the local demo server
python examples/demo_server.py
redirect-chain-fixer --urls examples/urls.txt        # in a second terminal
```
