import io
import zipfile
import builtins

from paperinsight.core.extractor import DataExtractor
from paperinsight.llm.base import BaseLLM
from paperinsight.llm.longcat_client import LongcatClient
from paperinsight.parser.mineru import MinerUParser


class DummyLLM(BaseLLM):
    def __init__(self):
        self.calls = []

    def generate(self, prompt, max_tokens=None, temperature=0.7, **kwargs):
        self.calls.append(("generate", prompt))
        return "ok"

    def generate_json(self, prompt, max_tokens=None, temperature=0.7, **kwargs):
        self.calls.append(("generate_json", prompt))
        return {
            "paper_info": {},
            "devices": [],
            "data_source": {},
        }

    def is_available(self) -> bool:
        return True


class SequentialJSONLLM(BaseLLM):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, prompt, max_tokens=None, temperature=0.7, **kwargs):
        self.calls.append(("generate", prompt))
        return "ok"

    def generate_json(self, prompt, max_tokens=None, temperature=0.7, **kwargs):
        self.calls.append(("generate_json", prompt))
        if not self.responses:
            raise AssertionError("unexpected extra generate_json call")
        return self.responses.pop(0)

    def is_available(self) -> bool:
        return True


class MockResponse:
    def __init__(self, status_code=200, json_data=None, text="", content=b""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.content = content

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


def test_data_extractor_supports_longcat_provider(monkeypatch):
    dummy_llm = DummyLLM()

    def fake_create_llm_client(config):
        assert config["provider"] == "longcat"
        return dummy_llm

    monkeypatch.setattr(
        "paperinsight.core.extractor.create_llm_client",
        fake_create_llm_client,
    )

    extractor = DataExtractor(
        config={
            "llm": {
                "enabled": True,
                "provider": "longcat",
                "api_key": "lc-test-key",
                "longcat": {"model": "LongCat-Flash-Chat"},
            }
        }
    )

    assert extractor.llm is dummy_llm


def test_data_extractor_runs_bilingual_postprocess_for_text_fields(monkeypatch):
    llm = SequentialJSONLLM(
        [
            {
                "paper_info": {
                    "title": "Blue OLED with improved efficiency",
                    "optimization_strategy": "Interface engineering improves exciton confinement.",
                    "best_eqe": "22.1%",
                    "research_type": "OLED",
                    "emitter_type": "TADF",
                },
                "devices": [
                    {
                        "device_label": "Champion device",
                        "structure": "ITO/PEDOT:PSS/EML/TPBi/LiF/Al",
                        "eqe": "22.1%",
                        "notes": "Device prepared with optimized host ratio.",
                    }
                ],
                "data_source": {
                    "eqe_source": "The champion device achieved a maximum EQE of 22.1%.",
                    "structure_source": "The device structure was ITO/PEDOT:PSS/EML/TPBi/LiF/Al.",
                },
                "optimization": {
                    "level": "interface engineering",
                    "strategy": "A thin interlayer balances charges and suppresses quenching.",
                    "key_findings": "The interlayer raises EQE without shifting emission color.",
                },
            },
            {
                "paper_info": {
                    "title": "中文：高效率蓝光 OLED\nEnglish: Blue OLED with improved efficiency",
                    "optimization_strategy": "中文：界面工程提升激子限制能力\nEnglish: Interface engineering improves exciton confinement.",
                    "best_eqe": "22.1%",
                    "research_type": "OLED",
                    "emitter_type": "TADF",
                },
                "devices": [
                    {
                        "device_label": "中文：冠军器件\nEnglish: Champion device",
                        "structure": "ITO/PEDOT:PSS/EML/TPBi/LiF/Al",
                        "eqe": "22.1%",
                        "notes": "中文：器件采用优化主材配比制备\nEnglish: Device prepared with optimized host ratio.",
                    }
                ],
                "data_source": {
                    "eqe_source": "中文：冠军器件获得 22.1% 的最大 EQE。\nEnglish: The champion device achieved a maximum EQE of 22.1%.",
                    "structure_source": "中文：器件结构为 ITO/PEDOT:PSS/EML/TPBi/LiF/Al。\nEnglish: The device structure was ITO/PEDOT:PSS/EML/TPBi/LiF/Al.",
                },
                "optimization": {
                    "level": "中文：界面工程\nEnglish: Interface engineering",
                    "strategy": "中文：超薄中间层平衡电荷并抑制猝灭。\nEnglish: A thin interlayer balances charges and suppresses quenching.",
                    "key_findings": "中文：中间层在不改变发光颜色的前提下提升 EQE。\nEnglish: The interlayer raises EQE without shifting emission color.",
                },
            },
        ]
    )

    monkeypatch.setattr(
        "paperinsight.core.extractor.create_llm_client",
        lambda config: llm,
    )

    extractor = DataExtractor(
        config={
            "llm": {
                "enabled": True,
                "provider": "longcat",
                "api_key": "lc-test-key",
                "longcat": {"model": "LongCat-Flash-Chat"},
            },
            "output": {
                "bilingual_text": True,
            },
        }
    )

    result = extractor.extract(
        markdown_text="# Title\n\ntext",
        cleaned_text="Blue OLED with improved efficiency",
    )

    assert result.success is True
    assert result.data.paper_info.title == "中文：高效率蓝光 OLED\nEnglish: Blue OLED with improved efficiency"
    assert result.data.optimization.level == "中文：界面工程\nEnglish: Interface engineering"
    assert (
        result.data.data_source.eqe_source
        == "中文：冠军器件获得 22.1% 的最大 EQE。\nEnglish: The champion device achieved a maximum EQE of 22.1%."
    )
    assert result.data.devices[0].structure == "ITO/PEDOT:PSS/EML/TPBi/LiF/Al"
    assert len(llm.calls) == 2
    assert "paper_info" in llm.calls[1][1]


def test_longcat_client_falls_back_to_http_when_openai_not_installed(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("openai not installed")
        return original_import(name, *args, **kwargs)

    def fake_post(url, headers=None, json=None, timeout=None, stream=False):
        assert url == "https://api.longcat.chat/openai/v1/chat/completions"
        assert headers["Authorization"] == "Bearer lc-test-key"
        assert json["model"] == "LongCat-Flash-Chat"
        return MockResponse(
            status_code=200,
            json_data={
                "choices": [
                    {
                        "message": {
                            "content": '{"paper_info": {}, "devices": [], "data_source": {}}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr("paperinsight.llm.longcat_client.requests.post", fake_post)

    client = LongcatClient(api_key="lc-test-key")

    result = client.generate_json("test prompt")

    assert result == {"paper_info": {}, "devices": [], "data_source": {}}


def test_mineru_parser_api_uses_v4_batch_upload_flow(monkeypatch, tmp_path):
    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake pdf")

    parser = MinerUParser(
        {
            "mode": "api",
            "token": "mineru-token",
            "api_url": "https://mineru.net/api",
            "timeout": 30,
            "extract_tables": True,
        }
    )

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("result/full.md", "# Abstract\n\nMinerU markdown output")
        archive.writestr("result/tables/device.csv", "name,eqe\nDevice A,20.5%\n")
    archive_bytes = archive_buffer.getvalue()

    calls = {"post": [], "put": [], "get": []}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"].append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return MockResponse(
            json_data={
                "code": 0,
                "data": {
                    "batch_id": "batch-123",
                    "file_urls": ["https://upload.example.com/file-1"],
                },
                "msg": "ok",
            }
        )

    def fake_put(url, data=None, timeout=None):
        calls["put"].append({"url": url, "timeout": timeout, "payload": data.read()})
        return MockResponse(status_code=200)

    def fake_get(url, headers=None, timeout=None):
        calls["get"].append({"url": url, "headers": headers, "timeout": timeout})
        if url == "https://mineru.net/api/v4/extract-results/batch/batch-123":
            return MockResponse(
                json_data={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-123",
                        "extract_result": [
                            {
                                "file_name": "demo.pdf",
                                "state": "done",
                                "data_id": "demo",
                                "full_zip_url": "https://download.example.com/result.zip",
                            }
                        ],
                    },
                    "msg": "ok",
                }
            )
        if url == "https://download.example.com/result.zip":
            return MockResponse(status_code=200, content=archive_bytes)
        raise AssertionError(f"unexpected GET url: {url}")

    monkeypatch.setattr("paperinsight.parser.mineru.requests.post", fake_post)
    monkeypatch.setattr("paperinsight.parser.mineru.requests.put", fake_put)
    monkeypatch.setattr("paperinsight.parser.mineru.requests.get", fake_get)

    result = parser.parse(pdf_path)

    assert result.success is True
    assert result.markdown == "# Abstract\n\nMinerU markdown output"
    assert result.tables[0].headers == ["name", "eqe"]
    assert result.metadata["batch_id"] == "batch-123"
    assert calls["post"][0]["url"] == "https://mineru.net/api/v4/file-urls/batch"
    assert calls["post"][0]["headers"]["Authorization"] == "Bearer mineru-token"
    assert calls["post"][0]["json"]["model_version"] == "vlm"
    assert calls["put"][0]["url"] == "https://upload.example.com/file-1"
    assert calls["get"][0]["url"] == "https://mineru.net/api/v4/extract-results/batch/batch-123"


def test_mineru_parser_parse_batch_uses_batch_api(monkeypatch, tmp_path):
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"%PDF-1.4\na")
    pdf_b.write_bytes(b"%PDF-1.4\nb")

    parser = MinerUParser(
        {
            "mode": "api",
            "token": "mineru-token",
            "api_url": "https://mineru.net/api/v4",
            "timeout": 30,
        }
    )

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("full.md", "# Results\n\nBatch markdown output")
    archive_bytes = archive_buffer.getvalue()

    post_calls = []
    put_calls = []
    progress_events = []

    def fake_post(url, headers=None, json=None, timeout=None):
        post_calls.append({"url": url, "json": json})
        return MockResponse(
            json_data={
                "code": 0,
                "data": {
                    "batch_id": "batch-group-1",
                    "file_urls": [
                        "https://upload.example.com/a",
                        "https://upload.example.com/b",
                    ],
                },
            }
        )

    def fake_put(url, data=None, timeout=None):
        put_calls.append(url)
        _ = data.read()
        return MockResponse(status_code=200)

    def fake_get(url, headers=None, timeout=None):
        if url == "https://mineru.net/api/v4/extract-results/batch/batch-group-1":
            return MockResponse(
                json_data={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-group-1",
                        "extract_result": [
                            {
                                "file_name": "a.pdf",
                                "state": "done",
                                "data_id": "a",
                                "full_zip_url": "https://download.example.com/a.zip",
                            },
                            {
                                "file_name": "b.pdf",
                                "state": "done",
                                "data_id": "b",
                                "full_zip_url": "https://download.example.com/b.zip",
                            },
                        ],
                    },
                }
            )
        if url in {"https://download.example.com/a.zip", "https://download.example.com/b.zip"}:
            return MockResponse(status_code=200, content=archive_bytes)
        raise AssertionError(f"unexpected GET url: {url}")

    monkeypatch.setattr("paperinsight.parser.mineru.requests.post", fake_post)
    monkeypatch.setattr("paperinsight.parser.mineru.requests.put", fake_put)
    monkeypatch.setattr("paperinsight.parser.mineru.requests.get", fake_get)

    results = parser.parse_batch(
        [pdf_a, pdf_b],
        progress_callback=lambda info: progress_events.append(info),
    )

    assert set(results.keys()) == {pdf_a, pdf_b}
    assert all(result.success for result in results.values())
    assert post_calls[0]["url"] == "https://mineru.net/api/v4/file-urls/batch"
    assert len(post_calls[0]["json"]["files"]) == 2
    assert put_calls == ["https://upload.example.com/a", "https://upload.example.com/b"]
    assert progress_events[-1]["done"] == 2
