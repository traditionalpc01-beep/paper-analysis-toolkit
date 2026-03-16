"""
报告生成器模块
功能: 生成 Excel 报告
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


class ReportGenerator:
    """报告生成器 v3.0
    
    按照 PRD 3.0 规范生成 Excel 报告：
    - 主信息列（标题、作者、IF）独占单元格
    - 多器件数据列（结构、EQE、CIE、寿命）使用 \n 换行拼接
    """

    REPORT_COLUMNS = [
        ("文件名 File", "file"),
        ("文件地址 URL", "url"),
        ("期刊名称 Journal", "journal"),
        ("影响因子 Impact Factor", "impact_factor"),
        ("作者 Authors", "authors"),
        ("论文标题 Title", "title"),
        ("器件结构 Device Structure", "structure"),
        ("EQE(外量子效率) EQE", "eqe"),
        ("色度坐标 CIE", "cie"),
        ("寿命 Lifetime", "lifetime"),
        ("最高EQE Best EQE", "best_eqe"),
        ("优化层级 Optimization Level", "optimization_level"),
        ("优化策略 Strategy Summary", "optimization_strategy"),
        ("优化详情 Optimization Details", "optimization_details"),
        ("关键发现 Key Findings", "key_findings"),
        ("EQE原文 EQE Source", "eqe_source"),
        ("CIE原文 CIE Source", "cie_source"),
        ("寿命原文 Lifetime Source", "lifetime_source"),
        ("结构原文 Structure Source", "structure_source"),
    ]

    FIELD_MAPPING = {
        "file": ("File", "file", "文件", "文件名"),
        "url": ("URL", "url", "文件地址"),
        "journal": ("journal_name", "期刊", "期刊名称"),
        "impact_factor": ("影响因子", "impact_factor"),
        "authors": ("authors", "作者"),
        "title": ("title", "标题", "论文标题"),
        "structure": ("器件结构", "device_structure", "结构"),
        "eqe": ("EQE", "eqe", "外量子效率"),
        "cie": ("CIE", "cie", "色度坐标"),
        "lifetime": ("寿命", "lifetime"),
        "best_eqe": ("最高EQE", "best_eqe"),
        "optimization_level": ("优化层级", "optimization_level"),
        "optimization_strategy": ("优化策略", "optimization_strategy"),
        "optimization_details": ("优化详情",),
        "key_findings": ("关键发现",),
        "eqe_source": ("EQE原文", "eqe_source"),
        "cie_source": ("CIE原文", "cie_source"),
        "lifetime_source": ("寿命原文", "lifetime_source"),
        "structure_source": ("结构原文", "structure_source"),
    }
    
    def __init__(self, output_dir: Union[str, Path]):
        """
        初始化报告生成器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_excel_report(
        self,
        results: list[dict],
        output_filename: Optional[str] = None,
        sort_by_if: bool = True,
    ) -> Path:
        """
        生成 Excel 报告
        
        Args:
            results: 提取结果列表
            output_filename: 输出文件名(可选)
            sort_by_if: 是否按影响因子排序
        
        Returns:
            生成的文件路径
        """
        # 生成文件名
        if output_filename is None:
            output_filename = self._build_default_filename("xlsx")

        output_path = self._build_unique_output_path(output_filename)
        
        # 创建工作簿
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "论文分析结果"
        
        # 样式定义
        header_fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11, name="Arial")
        cell_font = Font(size=10, name="Arial")
        thin_border = Border(
            left=Side(style="thin", color="BFBFBF"),
            right=Side(style="thin", color="BFBFBF"),
            top=Side(style="thin", color="BFBFBF"),
            bottom=Side(style="thin", color="BFBFBF"),
        )
        
        # 写入表头
        for col, (header, _) in enumerate(self.REPORT_COLUMNS, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
        
        # 排序
        if sort_by_if:
            results = sorted(results, key=self._sort_key_by_if, reverse=True)
        
        # 写入数据
        for row_idx, result in enumerate(results, 2):
            for col_idx, (_, field_key) in enumerate(self.REPORT_COLUMNS, 1):
                value = self._format_cell_value(result, field_key)
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = cell_font
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = thin_border
                
                # 高亮有数据的关键指标列
                if field_key in {"eqe", "cie", "lifetime"} and value:
                    cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        
        # 设置列宽 - 按照 PRD 3.0 规范
        column_widths = {
            "file": 30,
            "url": 45,
            "journal": 28,
            "impact_factor": 16,
            "authors": 25,
            "title": 50,
            "structure": 45,
            "eqe": 20,
            "cie": 20,
            "lifetime": 22,
            "best_eqe": 16,
            "optimization_level": 24,
            "optimization_strategy": 40,
            "optimization_details": 40,
            "key_findings": 40,
            "eqe_source": 50,
            "cie_source": 50,
            "lifetime_source": 50,
            "structure_source": 50,
        }

        for col_idx, (_, field_key) in enumerate(self.REPORT_COLUMNS, 1):
            width = column_widths.get(field_key, 20)
            ws.column_dimensions[get_column_letter(col_idx)].width = width
        
        # 设置行高
        ws.row_dimensions[1].height = 35
        for row in range(2, len(results) + 2):
            ws.row_dimensions[row].height = 80
        
        # 冻结首行
        ws.freeze_panes = "A2"
        
        # 保存
        wb.save(output_path)
        print(f"[报告] Excel 报告已保存: {output_path}")
        
        return output_path
    
    def _format_cell_value(self, result: dict, field_key: str) -> str:
        """
        格式化单元格值
        
        按照 PRD 3.0 规范：
        - 多器件数据列（结构、EQE、CIE、寿命）已在 to_excel_row() 中使用 \n 拼接
        - 数据溯源列拆分为独立的原文引用列
        
        Args:
            result: 提取结果
            field_key: 规范化字段名
        
        Returns:
            格式化后的值
        """
        # 多器件数据列 - 已在 PaperData.to_excel_row() 中处理为换行拼接格式
        if field_key == "optimization_level":
            optimization = result.get("optimization", {}) if isinstance(result.get("optimization"), dict) else {}
            return (
                result.get("优化层级")
                or result.get("optimization_level")
                or optimization.get("level")
                or ""
            )

        if field_key == "optimization_strategy":
            optimization = result.get("optimization", {}) if isinstance(result.get("optimization"), dict) else {}
            return (
                result.get("优化策略")
                or result.get("optimization_strategy")
                or optimization.get("strategy")
                or ""
            )

        if field_key == "optimization_details":
            return result.get("优化详情") or ""

        if field_key == "key_findings":
            optimization = result.get("optimization", {}) if isinstance(result.get("optimization"), dict) else {}
            return result.get("关键发现") or optimization.get("key_findings") or ""

        value = self._get_mapped_value(result, field_key)
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)

        if field_key == "impact_factor":
            return self._coerce_if_value(value)

        return str(value) if value not in (None, "") else ""
    
    def generate_json_report(
        self,
        results: list[dict],
        output_filename: Optional[str] = None,
        sort_by_if: bool = True,
    ) -> Path:
        """
        生成 JSON 报告
        
        Args:
            results: 提取结果列表
            output_filename: 输出文件名
            sort_by_if: 是否按影响因子排序
        
        Returns:
            生成的文件路径
        """
        if output_filename is None:
            output_filename = self._build_default_filename("json")

        output_path = self._build_unique_output_path(output_filename)
        
        if sort_by_if:
            results = sorted(results, key=self._sort_key_by_if, reverse=True)
        
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"[报告] JSON 报告已保存: {output_path}")
        
        return output_path
    
    def generate_error_log(
        self,
        errors: list[dict],
        output_filename: Optional[str] = None,
    ) -> Optional[Path]:
        """
        生成错误日志
        
        Args:
            errors: 错误列表
            output_filename: 输出文件名
        
        Returns:
            生成的文件路径(如果有错误)
        """
        if not errors:
            return None
        
        if output_filename is None:
            output_filename = "error_log.txt"
        
        output_path = self.output_dir / output_filename
        
        with output_path.open("w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("PaperInsight 错误日志\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"错误总数: {len(errors)}\n")
            f.write("=" * 70 + "\n\n")
            
            for idx, error in enumerate(errors, 1):
                f.write(f"[错误 {idx}]\n")
                f.write(f"时间: {error.get('timestamp', 'N/A')}\n")
                f.write(f"文件: {error.get('pdf_name', 'N/A')}\n")
                f.write(f"类型: {error.get('error_type', 'N/A')}\n")
                f.write(f"信息: {error.get('error_message', 'N/A')}\n")
                if error.get('context'):
                    f.write(f"上下文: {error['context']}\n")
                f.write("-" * 70 + "\n\n")
        
        print(f"[错误日志] 已保存: {output_path}")
        
        return output_path

    def _get_mapped_value(self, result: dict, field_key: str):
        for key in self.FIELD_MAPPING.get(field_key, (field_key,)):
            if key in result and result[key] not in (None, ""):
                return result[key]
        return ""

    def _sort_key_by_if(self, result: dict) -> float:
        return self._coerce_if_value(self._get_mapped_value(result, "impact_factor"))

    def _build_default_filename(self, extension: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"论文分析报告_{timestamp}"
        return f"{base_name}.{extension}"

    def _build_unique_output_path(self, output_filename: str) -> Path:
        output_path = self.output_dir / output_filename
        if not output_path.exists():
            return output_path

        stem = output_path.stem
        suffix = output_path.suffix
        counter = 1
        while True:
            candidate = self.output_dir / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _coerce_if_value(value) -> float:
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            match = __import__("re").search(r"([0-9]+(?:\.[0-9]+)?)", value)
            if match:
                return float(match.group(1))

        return 0.0
