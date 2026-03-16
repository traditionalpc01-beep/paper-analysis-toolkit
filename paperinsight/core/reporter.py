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

    FIELD_MAPPING = {
        "File": ("File",),
        "URL": ("URL",),
        "期刊名称": ("journal_name", "期刊", "期刊名称"),
        "影响因子": ("影响因子", "impact_factor"),
        "作者": ("authors", "作者"),
        "论文标题": ("title", "标题", "论文标题"),
        "器件结构": ("device_structure", "器件结构", "结构"),
        "EQE(外量子效率)": ("eqe", "EQE", "外量子效率"),
        "色度坐标": ("cie", "CIE", "色度坐标"),
        "寿命": ("lifetime", "寿命"),
        "补充信息": ("supplementary_info", "补充信息"),
    }
    
    # 报告列定义 - 按照 PRD 3.0 规范排序
    REPORT_HEADERS = [
        "File",
        "URL",
        "期刊名称",
        "影响因子",
        "作者",
        "论文标题",
        "器件结构",
        "EQE(外量子效率)",
        "色度坐标",
        "寿命",
        "最高EQE",
        "优化策略",
        "优化详情",
        "关键发现",
        "EQE原文",
        "CIE原文",
        "寿命原文",
        "结构原文",
    ]
    
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
            output_filename = "Paper_Analysis_Report.xlsx"
        
        output_path = self.output_dir / output_filename
        
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
        for col, header in enumerate(self.REPORT_HEADERS, 1):
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
            for col_idx, header in enumerate(self.REPORT_HEADERS, 1):
                value = self._format_cell_value(result, header)
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = cell_font
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = thin_border
                
                # 高亮有数据的关键指标列
                if header in {"EQE(外量子效率)", "色度坐标", "寿命"} and value:
                    cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        
        # 设置列宽 - 按照 PRD 3.0 规范
        column_widths = {
            "File": 30,
            "URL": 40,
            "期刊名称": 25,
            "影响因子": 12,
            "作者": 25,
            "论文标题": 50,
            "器件结构": 45,  # 多器件数据可能较长
            "EQE(外量子效率)": 20,
            "色度坐标": 20,
            "寿命": 20,
            "最高EQE": 12,
            "优化策略": 40,
            "优化详情": 40,
            "关键发现": 40,
            "EQE原文": 50,
            "CIE原文": 50,
            "寿命原文": 50,
            "结构原文": 50,
        }
        
        for col_idx, header in enumerate(self.REPORT_HEADERS, 1):
            width = column_widths.get(header, 20)
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
    
    def _format_cell_value(self, result: dict, header: str) -> str:
        """
        格式化单元格值
        
        按照 PRD 3.0 规范：
        - 多器件数据列（结构、EQE、CIE、寿命）已在 to_excel_row() 中使用 \n 拼接
        - 数据溯源列拆分为独立的原文引用列
        
        Args:
            result: 提取结果
            header: 列名
        
        Returns:
            格式化后的值
        """
        # 多器件数据列 - 已在 PaperData.to_excel_row() 中处理为换行拼接格式
        if header == "器件结构":
            return result.get("器件结构") or result.get("device_structure") or ""
        
        if header == "EQE(外量子效率)":
            return result.get("EQE") or result.get("eqe") or ""
        
        if header == "色度坐标":
            return result.get("CIE") or result.get("cie") or ""
        
        if header == "寿命":
            return result.get("寿命") or result.get("lifetime") or ""
        
        # 最高 EQE
        if header == "最高EQE":
            return result.get("最高EQE") or result.get("best_eqe") or ""
        
        # 优化策略相关
        if header == "优化策略":
            return result.get("优化策略") or result.get("optimization_strategy") or ""
        
        if header == "优化详情":
            return result.get("优化详情") or ""
        
        if header == "关键发现":
            return result.get("关键发现") or ""
        
        # 数据溯源原文列
        if header == "EQE原文":
            return result.get("EQE原文") or result.get("eqe_source") or ""
        
        if header == "CIE原文":
            return result.get("CIE原文") or result.get("cie_source") or ""
        
        if header == "寿命原文":
            return result.get("寿命原文") or result.get("lifetime_source") or ""
        
        if header == "结构原文":
            return result.get("结构原文") or result.get("structure_source") or ""
        
        # 一般字段
        value = self._get_mapped_value(result, header)
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)

        if header == "影响因子":
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
            output_filename = "Paper_Analysis_Report.json"
        
        output_path = self.output_dir / output_filename
        
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

    def _get_mapped_value(self, result: dict, header: str):
        for key in self.FIELD_MAPPING.get(header, (header,)):
            if key in result and result[key] not in (None, ""):
                return result[key]
        return ""

    def _sort_key_by_if(self, result: dict) -> float:
        return self._coerce_if_value(self._get_mapped_value(result, "影响因子"))

    @staticmethod
    def _coerce_if_value(value) -> float:
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            match = __import__("re").search(r"([0-9]+(?:\.[0-9]+)?)", value)
            if match:
                return float(match.group(1))

        return 0.0
