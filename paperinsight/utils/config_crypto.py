"""
配置加密模块
功能: 加密存储敏感配置信息(API Key等)
"""

import base64
import hashlib
import os
from pathlib import Path
from typing import Optional, Union


def _get_key_file_path() -> Path:
    """获取加密密钥文件路径"""
    config_dir = Path.home() / ".paperinsight"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / ".key"


def _get_machine_id() -> str:
    """
    获取机器唯一标识
    
    Returns:
        基于机器信息的哈希值
    """
    import platform
    
    # 组合机器信息
    machine_info = [
        platform.node(),  # 计算机名
        platform.machine(),  # 机器类型
        platform.processor(),  # 处理器信息
        str(Path.home()),  # 用户主目录
    ]
    
    # 生成哈希
    combined = "|".join(machine_info)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def _generate_key() -> bytes:
    """
    生成或加载加密密钥
    
    Returns:
        32字节加密密钥
    """
    key_file = _get_key_file_path()
    
    if key_file.exists():
        # 加载已有密钥
        key_data = base64.b64decode(key_file.read_text(encoding="utf-8"))
        
        # 验证密钥是否属于当前机器
        machine_id = _get_machine_id()
        if len(key_data) > 32:
            stored_machine_id = key_data[:32].decode("utf-8", errors="ignore")
            if stored_machine_id == machine_id:
                return key_data[32:]
    
    # 生成新密钥
    import secrets
    key = secrets.token_bytes(32)
    
    # 保存密钥(前缀加上机器ID用于验证)
    machine_id = _get_machine_id().encode()
    key_data = base64.b64encode(machine_id + key).decode("utf-8")
    key_file.write_text(key_data, encoding="utf-8")
    
    # 设置文件权限(仅当前用户可读写)
    os.chmod(key_file, 0o600)
    
    return key


def _simple_encrypt(plaintext: str, key: bytes) -> str:
    """
    简单加密函数(XOR + Base64)
    
    Args:
        plaintext: 明文
        key: 加密密钥
    
    Returns:
        Base64编码的密文
    """
    # 将明文转换为字节
    data = plaintext.encode("utf-8")
    
    # XOR加密
    encrypted = bytearray()
    for i, byte in enumerate(data):
        encrypted.append(byte ^ key[i % len(key)])
    
    # Base64编码
    return base64.b64encode(bytes(encrypted)).decode("utf-8")


def _simple_decrypt(ciphertext: str, key: bytes) -> str:
    """
    简单解密函数
    
    Args:
        ciphertext: Base64编码的密文
        key: 加密密钥
    
    Returns:
        明文
    """
    try:
        # Base64解码
        data = base64.b64decode(ciphertext)
        
        # XOR解密
        decrypted = bytearray()
        for i, byte in enumerate(data):
            decrypted.append(byte ^ key[i % len(key)])
        
        return bytes(decrypted).decode("utf-8")
    except Exception:
        return ""


def encrypt_config_value(value: str) -> str:
    """
    加密配置值
    
    Args:
        value: 明文值
    
    Returns:
        加密后的值(带前缀标识)
    """
    if not value:
        return value
    
    # 如果已经是加密格式,直接返回
    if value.startswith("ENC:"):
        return value
    
    key = _generate_key()
    encrypted = _simple_encrypt(value, key)
    return f"ENC:{encrypted}"


def decrypt_config_value(value: str) -> str:
    """
    解密配置值
    
    Args:
        value: 加密值
    
    Returns:
        明文值
    """
    if not value or not isinstance(value, str):
        return value
    
    # 检查是否是加密格式
    if not value.startswith("ENC:"):
        return value
    
    # 提取密文
    ciphertext = value[4:]  # 去掉 "ENC:" 前缀
    
    try:
        key = _generate_key()
        return _simple_decrypt(ciphertext, key)
    except Exception:
        return value


def encrypt_sensitive_fields(config: dict, fields: Optional[list[str]] = None) -> dict:
    """
    加密配置中的敏感字段
    
    Args:
        config: 配置字典
        fields: 需要加密的字段列表
    
    Returns:
        加密后的配置字典
    """
    if fields is None:
        fields = [
            "baidu_api_key",
            "baidu_secret_key",
            "llm_api_key",
            "api_key",
            "secret_key",
        ]
    
    encrypted_config = {}
    for key, value in config.items():
        if isinstance(value, dict):
            # 递归处理嵌套字典
            encrypted_config[key] = encrypt_sensitive_fields(value, fields)
        elif isinstance(value, str) and any(f in key.lower() for f in fields):
            # 加密敏感字段
            encrypted_config[key] = encrypt_config_value(value)
        else:
            encrypted_config[key] = value
    
    return encrypted_config


def decrypt_sensitive_fields(config: dict) -> dict:
    """
    解密配置中的敏感字段
    
    Args:
        config: 配置字典
    
    Returns:
        解密后的配置字典
    """
    decrypted_config = {}
    for key, value in config.items():
        if isinstance(value, dict):
            # 递归处理嵌套字典
            decrypted_config[key] = decrypt_sensitive_fields(value)
        elif isinstance(value, str):
            # 解密字段
            decrypted_config[key] = decrypt_config_value(value)
        else:
            decrypted_config[key] = value
    
    return decrypted_config
