"""
哈希工具模块
功能: 计算文件 MD5 指纹
"""

import hashlib
from pathlib import Path
from typing import Union


def calculate_md5(file_path: Union[str, Path], chunk_size: int = 8192) -> str:
    """
    计算文件的 MD5 哈希值
    
    Args:
        file_path: 文件路径
        chunk_size: 读取块大小(字节)
    
    Returns:
        MD5 哈希值(32位十六进制字符串)
    
    Example:
        >>> md5 = calculate_md5("paper.pdf")
        >>> print(md5)
        'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    md5_hash = hashlib.md5()
    
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            md5_hash.update(chunk)
    
    return md5_hash.hexdigest()


def calculate_text_md5(text: str) -> str:
    """
    计算文本的 MD5 哈希值
    
    Args:
        text: 文本内容
    
    Returns:
        MD5 哈希值(32位十六进制字符串)
    """
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def verify_file_integrity(file_path: Union[str, Path], expected_md5: str) -> bool:
    """
    验证文件完整性
    
    Args:
        file_path: 文件路径
        expected_md5: 预期的 MD5 值
    
    Returns:
        是否匹配
    """
    actual_md5 = calculate_md5(file_path)
    return actual_md5.lower() == expected_md5.lower()
