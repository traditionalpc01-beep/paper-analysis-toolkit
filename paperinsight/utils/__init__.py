"""工具模块。"""

__all__ = [
    "PDFProcessor",
    "calculate_md5",
    "setup_logger",
    "FileRenamer",
    "create_renamer",
    "EnvironmentChecker",
    "check_environment",
    "get_run_mode",
]


def __getattr__(name: str):
    if name == "PDFProcessor":
        from paperinsight.utils.pdf_utils import PDFProcessor
        return PDFProcessor
    if name == "calculate_md5":
        from paperinsight.utils.hash_utils import calculate_md5
        return calculate_md5
    if name == "setup_logger":
        from paperinsight.utils.logger import setup_logger
        return setup_logger
    if name == "FileRenamer":
        from paperinsight.utils.file_renamer import FileRenamer
        return FileRenamer
    if name == "create_renamer":
        from paperinsight.utils.file_renamer import create_renamer
        return create_renamer
    if name == "EnvironmentChecker":
        from paperinsight.utils.env_checker import EnvironmentChecker
        return EnvironmentChecker
    if name == "check_environment":
        from paperinsight.utils.env_checker import check_environment
        return check_environment
    if name == "get_run_mode":
        from paperinsight.utils.env_checker import get_run_mode
        return get_run_mode
    raise AttributeError(name)
