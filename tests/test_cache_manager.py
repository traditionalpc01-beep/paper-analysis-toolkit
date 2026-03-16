from paperinsight.core.cache import CacheManager


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
