import unittest

from zxt_notify import EmailSettings, NotificationError, build_email_message, render_email_html, send_email


class FakeSmtp:
    instance = None

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in = None
        self.message = None
        FakeSmtp.instance = self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self, context):
        self.started_tls = context is not None

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message):
        self.message = message


class MailerTests(unittest.TestCase):
    def setUp(self):
        self.settings = EmailSettings(
            host="smtp.example.test",
            port=587,
            sender="intel@example.test",
            default_to="owner@example.test",
            username="robot",
            password="secret",
            use_tls=True,
        )

    def test_alert_message_has_plain_and_html_parts(self):
        message = build_email_message("alert", "召回预警", "影响：供应链\n建议：立即核验", None, self.settings)
        self.assertEqual(message["To"], "owner@example.test")
        self.assertTrue(message.is_multipart())
        self.assertIn("召回预警", message.get_body(preferencelist=("html",)).get_content())

    def test_daily_template_renders_six_sections(self):
        body = "\n".join(f"## 标题{i}\n内容{i}" for i in range(1, 7))
        html = render_email_html("daily", "行业周报", body)
        self.assertEqual(html.count("<section"), 6)
        self.assertIn("行业周报", html)

    def test_send_email_uses_tls_and_login(self):
        result = send_email(
            "alert",
            "风险事件",
            "正文",
            "a@example.test;b@example.test",
            settings=self.settings,
            smtp_factory=FakeSmtp,
        )
        self.assertEqual(result, "[email:alert] 风险事件")
        self.assertTrue(FakeSmtp.instance.started_tls)
        self.assertEqual(FakeSmtp.instance.logged_in, ("robot", "secret"))
        self.assertEqual(FakeSmtp.instance.message["To"], "a@example.test, b@example.test")

    def test_empty_recipient_is_rejected(self):
        settings = EmailSettings(host="localhost", default_to="")
        with self.assertRaisesRegex(NotificationError, "收件人"):
            build_email_message("alert", "主题", "正文", None, settings)


if __name__ == "__main__":
    unittest.main()
