"""
文件重命名模块
功能: 自动重命名归档 PDF 文件
"""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


logger = logging.getLogger("paperinsight.file_renamer")


class FileRenamer:
    """文件重命名器"""
    
    def __init__(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
    ):
        """
        初始化文件重命名器
        
        Args:
            output_dir: 输出目录(如果为 None,则在原目录重命名)
            dry_run: 是否只预览不执行
        """
        self.output_dir = Path(output_dir) if output_dir else None
        self.dry_run = dry_run
    
    def generate_new_name(
        self,
        original_path: Union[str, Path],
        result: dict,
        format_template: str = "[{year}_{impact_factor}_{journal}]_{title}.pdf",
    ) -> str:
        """
        生成新文件名
        
        Args:
            original_path: 原文件路径
            result: 提取结果
            format_template: 文件名模板
        
        Returns:
            新文件名
        """
        path = Path(original_path)
        
        # 提取年份
        year = self._extract_year(result, path)
        
        # 提取影响因子
        if_value = result.get("影响因子", 0) or 0
        if_str = f"IF{if_value:.1f}" if if_value else "IF未知"
        
        # 提取期刊名(简化)
        journal = result.get("journal_name", "") or result.get("期刊名称", "")
        journal_short = self._shorten_journal_name(journal)
        
        # 提取标题
        title = result.get("title", "") or result.get("论文标题", "")
        title_clean = self._clean_title(title)
        
        # 替换模板变量
        template_values = {
            "year": year,
            "impact_factor": if_str,
            "if": if_str,
            "journal": journal_short,
            "title": title_clean[:100],
        }
        new_name = format_template.format_map(template_values)
        
        # 清理文件名
        new_name = self._sanitize_filename(new_name)
        
        return new_name
    
    def rename_file(
        self,
        original_path: Union[str, Path],
        result: dict,
        format_template: str = "[{year}_{impact_factor}_{journal}]_{title}.pdf",
    ) -> Optional[Path]:
        """
        重命名文件
        
        Args:
            original_path: 原文件路径
            result: 提取结果
            format_template: 文件名模板
        
        Returns:
            新文件路径(如果成功)
        """
        path = Path(original_path)
        if not path.exists():
            return None
        
        # 生成新文件名
        new_name = self.generate_new_name(path, result, format_template)
        
        # 确定输出路径
        if self.output_dir:
            new_path = self.output_dir / new_name
        else:
            new_path = path.parent / new_name
        
        # 检查文件是否已存在
        if new_path.exists() and new_path != path:
            # 添加序号
            counter = 1
            while new_path.exists():
                stem = new_path.stem
                new_path = new_path.parent / f"{stem}_{counter}{new_path.suffix}"
                counter += 1
        
        # 执行重命名
        if not self.dry_run:
            try:
                path.rename(new_path)
                return new_path
            except Exception as e:
                logger.warning(f"[RenameFailed] {path.name}: {e}")
                return None
        else:
            logger.info(f"[RenamePreview] {path.name} -> {new_name}")
            return new_path
    
    def batch_rename(
        self,
        pdf_results: list[tuple[Path, dict]],
        format_template: str = "[{year}_{impact_factor}_{journal}]_{title}.pdf",
    ) -> list[tuple[Path, Optional[Path]]]:
        """
        批量重命名
        
        Args:
            pdf_results: (PDF 路径, 提取结果) 列表
            format_template: 文件名模板
        
        Returns:
            (原路径, 新路径) 列表
        """
        results = []
        
        for pdf_path, result in pdf_results:
            new_path = self.rename_file(pdf_path, result, format_template)
            results.append((pdf_path, new_path))
        
        return results
    
    def _extract_year(self, result: dict, path: Path) -> str:
        """提取年份"""
        # 尝试从结果中提取
        if result.get("year"):
            return str(result["year"])
        
        # 尝试从文件名提取
        name = path.stem
        year_match = re.search(r'\b(19|20)\d{2}\b', name)
        if year_match:
            return year_match.group(0)
        
        # 使用当前年份
        return str(datetime.now().year)
    
    def _shorten_journal_name(self, journal: str) -> str:
        """简化期刊名称"""
        if not journal or journal == "未知期刊":
            return "Unknown"
        
        # 常见期刊缩写
        abbreviations = {
            "Nature Communications": "NatCommun",
            "Nature Materials": "NatMater",
            "Nature Photonics": "NatPhoton",
            "Nature Nanotechnology": "NatNano",
            "Advanced Materials": "AdvMater",
            "Advanced Functional Materials": "AdvFunctMater",
            "Journal of the American Chemical Society": "JACS",
            "ACS Nano": "ACSNano",
            "Nano Letters": "NanoLett",
        }
        
        if journal in abbreviations:
            return abbreviations[journal]
        
        # 移除常见词
        short = journal
        for word in ["The ", "Journal of ", " and ", " International"]:
            short = short.replace(word, " ")
        
        # 取首字母缩写
        words = short.split()
        if len(words) > 3:
            return "".join(w[0] for w in words[:4]).upper()
        
        return "".join(words[:3])[:20]
    
    def _clean_title(self, title: str) -> str:
        """清理标题"""
        if not title or title == "未提取到标题":
            return "Untitled"
        
        # 移除特殊字符
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        title = re.sub(r'\s+', '_', title)
        
        return title.strip("_")
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        # 移除不允许的字符
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # 替换多个下划线
        filename = re.sub(r'_+', '_', filename)
        # 移除首尾空格和下划线
        filename = filename.strip(' _')
        
        return filename


def create_renamer(
    output_dir: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
) -> FileRenamer:
    """
    创建文件重命名器
    
    Args:
        output_dir: 输出目录
        dry_run: 是否只预览
    
    Returns:
        FileRenamer 实例
    """
    return FileRenamer(output_dir=output_dir, dry_run=dry_run)
