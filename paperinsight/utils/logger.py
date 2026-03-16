"""
日志系统模块
功能: 配置和管理日志
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union
from datetime import datetime


def setup_logger(
    name: str = "paperinsight",
    level: int = logging.INFO,
    log_file: Optional[Union[str, Path]] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径(可选)
        format_string: 日志格式字符串
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 默认格式
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    
    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器(如果指定)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_error_log_path(output_dir: Union[str, Path]) -> Path:
    """
    获取错误日志文件路径
    
    Args:
        output_dir: 输出目录
    
    Returns:
        错误日志文件路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    return output_path / "error_log.txt"


class ErrorLogger:
    """错误日志记录器"""
    
    def __init__(self, output_dir: Union[str, Path]):
        self.log_path = get_error_log_path(output_dir)
        self.errors: list[dict] = []
    
    def log_error(self, pdf_name: str, error: Exception, context: str = ""):
        """记录错误"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "pdf_name": pdf_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
        }
        self.errors.append(error_info)
    
    def save(self):
        """保存错误日志"""
        if not self.errors:
            return
        
        with self.log_path.open("w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("PaperInsight 错误日志\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"错误总数: {len(self.errors)}\n")
            f.write("=" * 70 + "\n\n")
            
            for idx, error in enumerate(self.errors, 1):
                f.write(f"[错误 {idx}]\n")
                f.write(f"时间: {error['timestamp']}\n")
                f.write(f"文件: {error['pdf_name']}\n")
                f.write(f"类型: {error['error_type']}\n")
                f.write(f"信息: {error['error_message']}\n")
                if error['context']:
                    f.write(f"上下文: {error['context']}\n")
                f.write("-" * 70 + "\n\n")
        
        return self.log_path
