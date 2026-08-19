import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from zxt_notify import NotificationError, build_signed_webhook, render_dingtalk, send_dingtalk


ALERT = SimpleNamespace(
    company="XX汽车",
    title="宣布召回12万辆汽车",
    level=SimpleNamespace(value="high"),
    impact="可能影响品牌信誉及供应链订单",
    suggestion="核对本公司是否使用相关零部件",
)


class FakeResponse:
    def __init__(self, payload, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class DingTalkTests(unittest.TestCase):
    def test_locked_template(self):
        text = render_dingtalk(ALERT)
        self.assertEqual(text.splitlines()[0], "【智讯通·行业重要事件提醒】")
        self.assertIn("风险等级：high", text)
        self.assertIn("建议：核对本公司是否使用相关零部件", text)

    def test_send_checks_business_response(self):
        client = FakeClient(FakeResponse({"errcode": 0, "errmsg": "ok"}))
        text = send_dingtalk(ALERT, webhook="https://example.test/robot?access_token=x", client=client)
        self.assertIn("宣布召回12万辆汽车", text)
        self.assertEqual(client.calls[0][1]["json"]["msgtype"], "text")

    def test_send_rejects_dingtalk_error(self):
        client = FakeClient(FakeResponse({"errcode": 310000, "errmsg": "keywords not in content"}))
        with self.assertRaisesRegex(NotificationError, "机器人拒绝消息"):
            send_dingtalk(ALERT, webhook="https://example.test/robot", client=client)

    def test_missing_webhook_is_configuration_error(self):
        with self.assertRaisesRegex(NotificationError, "DINGTALK_WEBHOOK"):
            send_dingtalk(ALERT, webhook="")

    def test_signed_webhook_preserves_token(self):
        result = build_signed_webhook("https://example.test/robot?access_token=abc", "secret", 1700000000000)
        query = parse_qs(urlsplit(result).query)
        self.assertEqual(query["access_token"], ["abc"])
        self.assertEqual(query["timestamp"], ["1700000000000"])
        self.assertTrue(query["sign"][0])


if __name__ == "__main__":
    unittest.main()
