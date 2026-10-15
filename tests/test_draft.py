"""draft.py：prompt 原文、verified 规则、DeepSeek 参数与重试。"""
import requests

import common
import draft as d


class Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body or {}, text

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


ITEM = {"id": "x", "vendor": "Cursor", "title": "t", "source_url": "https://cursor.com/changelog", "verified": False, "summary_zh": ""}
OK = {"choices": [{"message": {"content": "摘要"}}]}


def test_prompt_contains_excerpt_and_rules():
    msg = d.build_messages(ITEM, "RELEASE NOTE TEXT")[1]["content"]
    assert "RELEASE NOTE TEXT" in msg
    assert "只使用下方「官方原文」" in msg
    assert "price_snapshot" in msg and "绝不能声称涨价、降价" in msg
    assert "计费周期变化" in msg


def test_source_excerpt_fetches_and_strips_html():
    got = d.source_excerpt(ITEM, fetch=lambda u: Resp(text="<p>Hello <b>world</b></p><script>x</script>"))
    assert got == "Hello world"
    assert d.source_excerpt(ITEM, fetch=lambda u: Resp(status=500)) == ""


def test_payload_disables_thinking_and_caps_tokens():
    p = d.build_payload(ITEM, "e", "m")
    assert p["thinking"] == {"type": "disabled"}
    assert p["max_tokens"] == d.MAX_TOKENS


def test_retry_on_429_5xx_then_success():
    seq = [Resp(429), Resp(503), Resp(200, OK)]
    sleeps = []
    out = d.summarize(ITEM, "u", "k", "m", "e", post=lambda *a, **k: seq.pop(0), sleep=sleeps.append)
    assert out == "摘要" and sleeps == [2.0, 4.0]


def test_retry_on_timeout_gives_up_after_max():
    calls = []

    def post(*a, **k):
        calls.append(1)
        raise requests.Timeout()

    try:
        d.summarize(ITEM, "u", "k", "m", "e", post=post, sleep=lambda s: None)
        assert False
    except requests.Timeout:
        pass
    assert len(calls) == d.MAX_ATTEMPTS


def test_no_retry_on_400():
    calls = []

    def post(*a, **k):
        calls.append(1)
        return Resp(400)

    try:
        d.summarize(ITEM, "u", "k", "m", "e", post=post, sleep=lambda s: None)
        assert False
    except requests.HTTPError:
        pass
    assert len(calls) == 1


def test_main_keeps_verified_false(monkeypatch):
    item = dict(ITEM)
    written = []
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setattr(common, "load_items", lambda: [item])
    monkeypatch.setattr(common, "enabled_sources", lambda *a: [{"official_domain": "cursor.com"}])
    monkeypatch.setattr(common, "write_item", written.append)
    monkeypatch.setattr(d, "source_excerpt", lambda it: "text")
    monkeypatch.setattr(d, "summarize", lambda *a, **k: "摘要")
    assert d.main() == 0
    assert written and written[0]["verified"] is False and written[0]["summary_zh"] == "摘要"


def test_main_skips_non_enabled_source(monkeypatch):
    item = dict(ITEM, source_url="https://evil.example/x")
    written = []
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setattr(common, "load_items", lambda: [item])
    monkeypatch.setattr(common, "enabled_sources", lambda *a: [{"official_domain": "cursor.com"}])
    monkeypatch.setattr(common, "write_item", written.append)
    monkeypatch.setattr(d, "summarize", lambda *a, **k: "摘要")
    assert d.main() == 0 and written == []
