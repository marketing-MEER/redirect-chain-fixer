import importlib.util
import tempfile
import threading
import unittest
from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from redirect_chain_fixer import cli, core

EXAMPLES = Path(__file__).parent.parent / "examples"


def demo_server():
    spec = importlib.util.spec_from_file_location("demo_server", EXAMPLES / "demo_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    srv = mod.server(port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def rules(rows):
    return pd.DataFrame(rows, columns=["source", "target", "status"])


class MapTest(unittest.TestCase):
    def test_chain_loop_self_and_dupes(self):
        f = core.flatten(rules([("/a", "/b", 301), ("/b", "/c", 301), ("/c", "/d", 302),
                                ("/x", "/y", 301), ("/y", "/x", 301), ("/s", "/s", 301),
                                ("/d1", "/e", 301), ("/d1", "/f", 301)])).set_index("source")
        self.assertEqual(f.at["/a", "final_target"], "/d")
        self.assertEqual(f.at["/a", "hops"], 3)
        self.assertIn("chain (3 hops)", f.at["/a", "issue"])
        self.assertIn("temporary", f.at["/a", "issue"])
        self.assertEqual(f.at["/x", "issue"], "loop")
        self.assertEqual(f.at["/s", "issue"], "redirects to itself")
        self.assertIn("listed more than once", f.loc["/d1", "issue"].iloc[0])
        self.assertEqual(f.at["/c", "issue"], "temporary redirect in path")

    def test_absolute_and_relative_match_on_one_host(self):
        f = core.flatten(rules([("https://site.com/a", "/b", 301), ("/b", "https://site.com/c", 301)]))
        self.assertEqual(f.iloc[0]["final_target"], "https://site.com/c")
        self.assertEqual(f.iloc[0]["hops"], 2)

    def test_rule_files(self):
        f = core.flatten(rules([("/a", "/b", 301), ("/b", "/c", 301), ("/q?id=1", "/a", 301)]))
        r = core.direct_rules(f, "source", "final_target")
        self.assertEqual(r["target"].tolist(), ["/c", "/c"])
        self.assertIn("Redirect 301 /a /c", core.htaccess(r))
        self.assertIn("location = /a { return 301 /c; }", core.nginx(r))
        self.assertIn("# /q?id=1 has a query string", core.htaccess(r))

    def test_load_map_and_empty(self):
        m = core.load_map(EXAMPLES / "redirects.csv")
        self.assertEqual(len(m), 14)
        self.assertEqual(m.iloc[5]["status"], 302)
        self.assertTrue(core.flatten(m.head(0)).empty)
        self.assertTrue(core.summary(core.flatten(m.head(0))).empty)


class LiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.base = demo_server()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_trace(self):
        b = self.base
        r = core.trace(f"{b}/features/crm", delay=0.5)
        self.assertEqual((r["redirects"], r["final_status"], r["final_url"]), (3, 200, f"{b}/platform"))
        self.assertEqual(core.trace(f"{b}/team")["issue"], "loop")
        self.assertEqual(core.trace(f"{b}/webinar-2024")["issue"], "ends in 404")
        self.assertEqual(core.trace(f"{b}/pricing")["redirects"], 0)

    def test_cli_both_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            urls = Path(tmp) / "urls.txt"
            urls.write_text((EXAMPLES / "urls.txt").read_text().replace("http://127.0.0.1:8001", self.base))
            out = Path(tmp) / "r"
            result = CliRunner().invoke(cli.main, ["--map", str(EXAMPLES / "redirects.csv"), "--urls", str(urls),
                                                   "-o", str(out)])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Redirect chain report", out.with_suffix(".html").read_text(encoding="utf-8"))
            sheets = pd.read_excel(out.with_suffix(".xlsx"), sheet_name=None)
            self.assertEqual(len(sheets["Direct rules"]), 4)        # live duplicates of map rules dropped
            self.assertIn("Redirect 301 /features/crm /platform", out.with_suffix(".htaccess").read_text())
            self.assertIn("Live all", sheets)


if __name__ == "__main__":
    unittest.main()
