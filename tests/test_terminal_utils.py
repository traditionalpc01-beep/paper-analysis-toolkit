import io

from paperinsight.utils.terminal import create_console, normalize_output_text


class DummyStream(io.StringIO):
    def __init__(self, encoding: str):
        super().__init__()
        self._encoding = encoding

    @property
    def encoding(self) -> str:
        return self._encoding

    def isatty(self) -> bool:
        return False


def test_normalize_output_text_falls_back_for_gbk_stream():
    stream = DummyStream("gbk")

    text = normalize_output_text("✓ 警告 ⚠ → 继续", stream)

    assert text == "[OK] 警告 [!] -> 继续"


def test_normalize_output_text_keeps_unicode_for_utf8_stream():
    stream = DummyStream("utf-8")

    text = normalize_output_text("✓ 警告 ⚠ → 继续", stream)

    assert text == "✓ 警告 ⚠ → 继续"


def test_create_console_writes_ascii_fallbacks_for_gbk_stream(monkeypatch):
    stream = DummyStream("gbk")
    monkeypatch.setattr("paperinsight.utils.terminal.sys.stdout", stream)

    console = create_console()
    console.print("✓ 启动成功 ⚠")

    assert "[OK] 启动成功 [!]" in stream.getvalue()
