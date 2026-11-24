import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)
import check_spec as cs  # noqa: E402

CODE = "\n".join([
    "class Order(Base):",                       # 1
    "    status = Column(String)",              # 2
    "",                                         # 3
    "def cancel(order):",                       # 4
    "    if order.status == 'pending':",        # 5
    "        order.status = 'cancelled'",       # 6
]) + "\n"

SPEC = """# Spec
## 读者
<!-- spec:section readers -->
- PM
## 实体
<!-- spec:section entities -->
- 订单有状态 [order.py:2](/app/order.py#L2 "status = Column(String)")
- 没有来源的事实
- 支付方式 〔未知〕
## 生命周期
<!-- spec:section lifecycles -->
来源：[order.py:4-6](/app/order.py#L4-L6)

| 从 | 到 |
|---|---|
| pending | cancelled |
- 取消 [order.py:5-6](/app/order.py#L5-L6 "order.status = 'cancelled'")
  - 子项由父项覆盖
## 建议
<!-- spec:section proposals -->
- 没有来源也可以
<!-- spec:prototype id=refund status=pending -->
"""


def run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "app"))
        os.makedirs(os.path.join(self.tmp, "docs", "spec"))
        self.write("app/order.py", CODE)
        self.write("docs/spec/spec.md", SPEC)
        run(["git", "init", "-q", "-b", "main"], self.tmp)
        run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A"], self.tmp)
        run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], self.tmp)
        self.spec_dir = os.path.join(self.tmp, "docs", "spec")

    def write(self, rel, text):
        with open(os.path.join(self.tmp, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def problems(self):
        p = []
        cs.check(cs.Spec(self.spec_dir, self.tmp), p)
        return p


class TestCheck(Base):
    def test_valid_links_pass_and_uncited_fact_is_warned(self):
        p = self.problems()
        self.assertEqual([x for x in p if x[0] == "error"], [])
        uncited = [x for x in p if "cites no code" in x[2]]
        self.assertEqual(len(uncited), 1, uncited)
        self.assertTrue(uncited[0][1].endswith(":8"))  # "没有来源的事实"

    def test_bad_quote_and_range_are_errors(self):
        self.write("docs/spec/spec.md", SPEC.replace('"status = Column(String)"', '"status = Integer"')
                   .replace("#L5-L6", "#L5-L60"))
        errs = [x[2] for x in self.problems() if x[0] == "error"]
        self.assertTrue(any("quote not found" in e for e in errs), errs)
        self.assertTrue(any("outside" in e for e in errs), errs)

    def test_escaped_quote_in_title(self):
        self.write("app/order.py", CODE + 'PREFIX = "/api"\n')
        self.write("docs/spec/spec.md", SPEC.replace("- 没有来源的事实",
                   '- 前缀 [order.py:7](/app/order.py#L7 "PREFIX = \\"/api\\"")'))
        p = self.problems()
        self.assertEqual([x for x in p if x[0] == "error"], [])
        self.assertFalse(any("cites no code" in x[2] for x in p))

    def test_missing_file_is_error(self):
        self.write("docs/spec/spec.md", SPEC.replace("/app/order.py#L2", "/app/nope.py#L2"))
        self.assertTrue(any("not found" in x[2] for x in self.problems() if x[0] == "error"))

    def test_pending_prototype_with_svg_is_error(self):
        os.makedirs(os.path.join(self.spec_dir, "prototypes"))
        self.write("docs/spec/prototypes/refund.svg", "<svg/>")
        self.assertTrue(any("still pending" in x[2] for x in self.problems() if x[0] == "error"))

    def test_confirmed_prototype_without_svg_is_warning(self):
        self.write("docs/spec/spec.md", SPEC.replace("status=pending", "status=confirmed"))
        self.assertTrue(any("draw prototypes/refund.svg" in x[2] for x in self.problems()))

    def test_pdf_missing_then_stale_is_warned(self):
        import render_pdf
        self.assertTrue(any("PDF missing" in x[2] for x in self.problems()))
        self.write("docs/spec/spec.pdf", "%PDF")
        self.write("docs/spec/" + render_pdf.FINGERPRINT, render_pdf.fingerprint(self.spec_dir))
        self.assertFalse(any(x[1] == "spec.pdf" for x in self.problems()))
        self.write("docs/spec/spec.md", SPEC + "\n新增一行\n")
        self.assertTrue(any("PDF older" in x[2] for x in self.problems()))

    def test_duplicates_found(self):
        self.write("docs/spec/spec.md", SPEC + "\n订单超过三十分钟未支付就会被系统自动取消。\n\n另外，订单超过三十分钟未支付就会被系统自动取消\n")
        self.assertTrue(cs.duplicates(cs.Spec(self.spec_dir, self.tmp)))


class TestMapRange(unittest.TestCase):
    def test_shift_and_affect(self):
        hunks = [(1, 0, 2, 3)]  # 3 lines inserted after old line 1
        self.assertEqual(cs.map_range(hunks, 4, 6), ("ok", (7, 9)))
        self.assertEqual(cs.map_range([(5, 1, 5, 1)], 4, 6)[0], "affected")
        self.assertEqual(cs.map_range([(10, 2, 10, 0)], 4, 6), ("ok", (4, 6)))
        self.assertEqual(cs.map_range([(2, 1, 1, 0)], 4, 6), ("ok", (3, 5)))  # line 2 deleted
        self.assertEqual(cs.map_range([(4, 0, 5, 1)], 4, 6)[0], "affected")  # insertion inside


class TestDiff(Base):
    def test_moved_lines_fixed_and_changed_lines_affected(self):
        self.write("app/order.py", "# header\n# header 2\n" + CODE.replace("'cancelled'", "'canceled'"))
        self.write("app/refund.py", "def refund(): pass\n")
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_spec.py"), self.spec_dir,
                              "--diff", "HEAD", "--fix-lines", "--json", os.path.join(self.tmp, "r.json")],
                             capture_output=True, text=True)
        with open(os.path.join(self.tmp, "r.json")) as fh:
            rep = json.load(fh)["diff"]
        self.assertEqual([m["lines"] for m in rep["moved"]], [[2, 2]])
        self.assertEqual({a["lines"][0] for a in rep["affected"]}, {4, 5})
        self.assertEqual([u["file"] for u in rep["uncovered"]], ["app/refund.py"])
        text = cs.read_lines(os.path.join(self.spec_dir, "spec.md"))
        text = "\n".join(text)
        self.assertIn("/app/order.py#L4 ", text)          # moved 2 -> 4, quote still matches
        self.assertIn("/app/order.py#L5-L6 ", text)       # affected links are not rewritten
        self.assertNotIn("quote not found in app/order.py:4", out.stdout)

    def test_rename_rewrites_path(self):
        run(["git", "mv", "app/order.py", "app/orders.py"], self.tmp)
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_spec.py"), self.spec_dir,
                        "--diff", "HEAD", "--fix-lines"], capture_output=True, text=True)
        text = cs.read_lines(os.path.join(self.spec_dir, "spec.md"))
        text = "\n".join(text)
        self.assertIn("/app/orders.py#L2", text)
        self.assertEqual([x for x in self.problems() if x[0] == "error"], [])


if __name__ == "__main__":
    unittest.main()
