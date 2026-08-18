import json
from paperinsight.core.cache import CacheManager, CACHE_SCHEMA_VERSION


def test_cache_manager_saves_markdown_with_new_filename(tmp_path):
    cache = CacheManager(tmp_path)
    md5 = "abc123"

    cache_path = cache.save_markdown_cache(md5, "# Title\n\ncontent")

    assert cache_path.name == "abc123_markdown.md"
    assert cache.has_markdown_cache(md5) is True
    assert cache.load_markdown_cache(md5) == "# Title\n\ncontent"


def test_cache_manager_reads_legacy_ocr_cache_for_backward_compatibility(tmp_path):
    cache = CacheManager(tmp_path)
    md5 = "legacy123"
    legacy_path = cache.get_ocr_cache_path(md5)
    legacy_path.write_text("legacy markdown", encoding="utf-8")

    assert cache.has_markdown_cache(md5) is True
    assert cache.load_markdown_cache(md5) == "legacy markdown"


# ── P2-4.6c: 缓存版本不兼容降级测试 ─────────────────────────


def test_cache_version_mismatch_returns_none(tmp_path):
    """缓存文件中 _cache_version 与当前版本不匹配时，load_data_cache 应返回 None。"""
    cache = CacheManager(tmp_path)
    md5 = "version_mismatch_test"

    # 写入一个旧版本的数据缓存
    data_cache_path = cache.get_data_cache_path(md5)
    old_data = {
        "paper_info": {"title": "Old Paper"},
        "_cache_version": CACHE_SCHEMA_VERSION - 1,  # 旧版本
        "_cache_timestamp": "2024-01-01T00:00:00",
        "_cache_md5": md5,
    }
    data_cache_path.write_text(json.dumps(old_data), encoding="utf-8")

    assert cache.has_data_cache(md5) is True
    loaded = cache.load_data_cache(md5)
    assert loaded is None


def test_cache_missing_version_field_returns_none(tmp_path):
    """缓存文件缺少 _cache_version 字段时，应返回 None（默认 version=0 != 1）。"""
    cache = CacheManager(tmp_path)
    md5 = "no_version_test"

    data_cache_path = cache.get_data_cache_path(md5)
    old_data = {"paper_info": {"title": "No Version Paper"}}
    data_cache_path.write_text(json.dumps(old_data), encoding="utf-8")

    assert cache.has_data_cache(md5) is True
    loaded = cache.load_data_cache(md5)
    assert loaded is None


def test_cache_broken_json_returns_none(tmp_path):
    """缓存文件 JSON 损坏时，应返回 None 而不是抛异常。"""
    cache = CacheManager(tmp_path)
    md5 = "broken_json_test"

    data_cache_path = cache.get_data_cache_path(md5)
    data_cache_path.write_text("{invalid json content!!!", encoding="utf-8")

    assert cache.has_data_cache(md5) is True
    loaded = cache.load_data_cache(md5)
    assert loaded is None


def test_cache_current_version_loads_successfully(tmp_path):
    """当前版本的缓存应正常加载。"""
    cache = CacheManager(tmp_path)
    md5 = "current_version_test"

    cache.save_data_cache(md5, {"paper_info": {"title": "Current Paper"}})
    loaded = cache.load_data_cache(md5)
    assert loaded is not None
    assert loaded["paper_info"]["title"] == "Current Paper"
    # 加载结果不应携带 _cache_* 元信息键（下游用 PaperData(extra='forbid') 反序列化）
    assert not any(k.startswith("_cache_") for k in loaded)


def test_cache_future_version_returns_none(tmp_path):
    """缓存文件中 _cache_version 高于当前版本（来自未来版本的工具）时应返回 None。"""
    cache = CacheManager(tmp_path)
    md5 = "future_version_test"

    data_cache_path = cache.get_data_cache_path(md5)
    future_data = {
        "paper_info": {"title": "Future Paper"},
        "_cache_version": CACHE_SCHEMA_VERSION + 10,
        "_cache_timestamp": "2026-12-01T00:00:00",
        "_cache_md5": md5,
    }
    data_cache_path.write_text(json.dumps(future_data), encoding="utf-8")

    loaded = cache.load_data_cache(md5)
    assert loaded is None


# ── 缓存统计与清理 ─────────────────────────────────────────


def test_cache_stats_reports_correctly(tmp_path):
    """缓存统计信息应正确反映缓存文件数量。"""
    cache = CacheManager(tmp_path)

    # 初始应为空
    stats = cache.get_cache_stats()
    assert stats["data_cache_count"] == 0
    assert stats["markdown_cache_count"] == 0

    # 添加缓存
    cache.save_data_cache("md5_1", {"title": "p1"})
    cache.save_data_cache("md5_2", {"title": "p2"})
    cache.save_markdown_cache("md5_1", "markdown text")

    stats = cache.get_cache_stats()
    assert stats["data_cache_count"] == 2
    assert stats["markdown_cache_count"] == 1


def test_clear_all_cache(tmp_path):
    """清除所有缓存应删除所有缓存文件。"""
    cache = CacheManager(tmp_path)
    cache.save_data_cache("md5_1", {"title": "p1"})
    cache.save_markdown_cache("md5_1", "text")
    cache.save_markdown_cache("md5_2", "text2")

    assert cache.has_data_cache("md5_1") is True
    assert cache.has_markdown_cache("md5_1") is True

    cache.clear_cache()

    assert cache.has_data_cache("md5_1") is False
    assert cache.has_markdown_cache("md5_1") is False


def test_clear_specific_cache(tmp_path):
    """清除指定 MD5 的缓存应只删除该 MD5 的文件。"""
    cache = CacheManager(tmp_path)
    cache.save_data_cache("md5_a", {"title": "a"})
    cache.save_data_cache("md5_b", {"title": "b"})

    cache.clear_cache("md5_a")

    assert cache.has_data_cache("md5_a") is False
    assert cache.has_data_cache("md5_b") is True


# ── P0 回归：数据缓存 round-trip ───────────────────────────


def test_cache_roundtrip_preserves_paper_data(tmp_path):
    """save -> load round-trip 后的数据必须能通过 PaperData(extra='forbid') 反序列化。

    回归防护：历史缺陷是 save 注入的 _cache_* 键残留在 load 结果中，
    导致 pipeline 的 PaperData(**cached_result) 永远抛 ValidationError，
    数据缓存形同虚设（每次都重新调 MinerU/LLM）。
    """
    from paperinsight.models.schemas import PaperData

    cache = CacheManager(tmp_path)
    md5 = "roundtrip_test"

    original = PaperData()
    original.paper_info.title = "InP Quantum Dot LEDs"
    original.paper_info.journal_name = "Nature Photonics"

    cache.save_data_cache(md5, original.model_dump())
    loaded = cache.load_data_cache(md5)

    assert loaded is not None
    restored = PaperData(**loaded)  # extra='forbid' 下不得抛 ValidationError
    assert restored.paper_info.title == "InP Quantum Dot LEDs"
    assert restored.paper_info.journal_name == "Nature Photonics"


def test_save_data_cache_does_not_mutate_caller_dict(tmp_path):
    """save 不应把 _cache_* 元信息键写进调用方传入的 dict。"""
    cache = CacheManager(tmp_path)
    data = {"paper_info": {"title": "X"}}

    cache.save_data_cache("md5_mut", data)

    assert "_cache_timestamp" not in data
    assert "_cache_md5" not in data
    assert "_cache_version" not in data
