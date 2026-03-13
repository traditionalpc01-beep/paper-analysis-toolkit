#!/usr/bin/env python3
"""
PDF论文分析工具 - 主脚本
功能：自动提取PDF论文中的关键信息并生成Excel报告
作者：WorkBuddy AI Assistant
版本：v1.1
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import openpyxl
import pdfplumber
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ============================================================================
# 配置区域
# ============================================================================

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# PDF文件所在目录（用户可以修改）
PDF_DIR = PROJECT_ROOT / "示例数据" / "pdfs"

# 输出目录（用户可以修改）
OUTPUT_DIR = PROJECT_ROOT / "输出结果"

# 是否使用已有的JSON数据（如果存在）
USE_EXISTING_JSON = True

# 期刊影响因子JSON配置文件
JOURNAL_CONFIG_PATH = PROJECT_ROOT / "配置文件" / "journal_impact_factors.json"

# ============================================================================
# 期刊影响因子数据库（2023-2024年数据，用户可自定义添加）
# ============================================================================

JOURNAL_IMPACT_FACTORS = {
    # 顶级期刊
    'Nature Communications': 16.6,
    'Nature': 64.8,
    'Nature Photonics': 39.7,
    'Nature Materials': 41.2,
    'Nature Nanotechnology': 38.3,
    'Science': 56.9,
    
    # 高影响因子期刊
    'Advanced Materials': 29.4,
    'Advanced Functional Materials': 19.0,
    'Advanced Optical Materials': 10.0,
    'ACS Nano': 17.1,
    'Nano Letters': 12.8,
    'Nano Today': 18.8,
    'Small': 13.3,
    'Small Methods': 12.4,
    
    # 化学和材料期刊
    'Journal of the American Chemical Society': 15.0,
    'JACS': 15.0,
    'ACS Applied Materials & Interfaces': 9.5,
    'Chemical Engineering Journal': 15.1,
    'ACS Applied Electronic Materials': 5.3,
    
    # 物理和光学期刊
    'Laser & Photonics Reviews': 10.9,
    'Optics Express': 3.8,
    'Optics Letters': 3.6,
    'Journal of Physical Chemistry C': 3.7,
    
    # 其他期刊（用户可添加）
    'Materials Today': 24.2,
    'Nano Research': 10.3,
    'Journal of Materials Chemistry C': 6.4,
    'Dalton Transactions': 4.1,
    'Physical Chemistry Chemical Physics': 3.7,
    'Journal of Photochemistry and Photobiology C': 12.1,
}

# ============================================================================
def load_journal_impact_factors(config_path, use_existing_json=True):
    """加载期刊影响因子配置"""
    impact_factors = dict(JOURNAL_IMPACT_FACTORS)

    if not use_existing_json or not config_path.exists():
        return impact_factors

    try:
        with config_path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[警告] 无法读取期刊配置文件 {config_path}: {exc}")
        return impact_factors

    for category, journals in config.items():
        if category == "说明" or not isinstance(journals, dict):
            continue

        for journal_name, info in journals.items():
            if isinstance(info, dict) and "impact_factor" in info:
                impact_factors[journal_name] = info["impact_factor"]
            elif isinstance(info, (int, float)):
                impact_factors[journal_name] = float(info)

    return impact_factors


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="批量分析 PDF 论文并导出 Excel 报告。"
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=PDF_DIR,
        help=f"PDF 输入目录，默认: {PDF_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Excel 输出目录，默认: {OUTPUT_DIR}",
    )
    parser.add_argument(
        "--journal-config",
        type=Path,
        default=JOURNAL_CONFIG_PATH,
        help=f"期刊影响因子 JSON 配置文件，默认: {JOURNAL_CONFIG_PATH}",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="不加载 JSON 期刊配置，仅使用脚本内置期刊数据。",
    )
    return parser.parse_args()


# 核心功能函数
# ============================================================================

def extract_full_text(pdf_path):
    """提取PDF全文"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
    except Exception as e:
        print(f"  错误: {e}")
        return ""

def extract_title(text, filename):
    """智能提取标题"""
    # 从文件名提取
    if ' - ' in filename:
        parts = filename.split(' - ')
        if len(parts) >= 3:
            title_from_name = parts[-1].replace('.pdf', '').strip()
            if len(title_from_name) > 20:
                return title_from_name
    
    # 从文本提取
    lines = text.split('\n')
    for i in range(min(20, len(lines))):
        line = lines[i].strip()
        if 20 < len(line) < 300 and not any(skip in line.lower() for skip in ['©', 'http', 'www.', 'vol.', 'issn', 'available']):
            if any(kw in line.lower() for kw in ['quantum', 'qled', 'led', 'dot', 'efficiency', 'inp', 'passivation', 'ligand', 'device', 'perovskite', 'solar']):
                return ' '.join(line.split())
    
    return "未提取到标题"

def extract_journal_info(text):
    """从PDF文本中提取期刊信息"""
    text_first_page = text[:3000]
    
    journal_patterns = [
        r'Nature Communications',
        r'Nature Materials',
        r'Nature Photonics',
        r'Advanced Materials',
        r'Advanced Functional Materials',
        r'Advanced Optical Materials',
        r'ACS Nano',
        r'Nano Letters',
        r'Nano Today',
        r'Small\s*(?:Methods)?',
        r'Chemical Engineering Journal',
        r'Materials Today',
        r'Laser\s*&?\s*Photonics Reviews',
        r'Journal of Photochemistry',
    ]
    
    for pattern in journal_patterns:
        match = re.search(pattern, text_first_page, re.IGNORECASE)
        if match:
            journal_name = match.group(0).strip()
            # 标准化期刊名称
            if 'nature communications' in journal_name.lower():
                return 'Nature Communications'
            elif 'nature materials' in journal_name.lower():
                return 'Nature Materials'
            elif 'nature photonics' in journal_name.lower():
                return 'Nature Photonics'
            elif 'advanced materials' in journal_name.lower() and 'functional' not in journal_name.lower() and 'optical' not in journal_name.lower():
                return 'Advanced Materials'
            elif 'advanced functional materials' in journal_name.lower():
                return 'Advanced Functional Materials'
            elif 'advanced optical materials' in journal_name.lower():
                return 'Advanced Optical Materials'
            elif 'acs nano' in journal_name.lower():
                return 'ACS Nano'
            elif 'nano letters' in journal_name.lower():
                return 'Nano Letters'
            elif 'small methods' in journal_name.lower():
                return 'Small Methods'
            elif 'small' in journal_name.lower():
                return 'Small'
            elif 'chemical engineering journal' in journal_name.lower():
                return 'Chemical Engineering Journal'
            elif 'materials today' in journal_name.lower():
                return 'Materials Today'
            elif 'laser' in journal_name.lower() and 'photonics' in journal_name.lower():
                return 'Laser & Photonics Reviews'
            elif 'journal of photochemistry' in journal_name.lower():
                return 'Journal of Photochemistry and Photobiology C'
            return journal_name
    
    return "未知期刊"

def extract_authors(text):
    """从PDF文本中提取作者信息"""
    text_first_page = text[:4000]
    lines = text_first_page.split('\n')
    
    authors = []
    for i, line in enumerate(lines[:30]):
        line = line.strip()
        if not line or len(line) < 5:
            continue
        
        if any(skip in line.lower() for skip in ['journal', 'doi', 'http', 'www', '©', 'vol.', 'issn']):
            continue
        
        if re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+', line):
            cleaned = re.sub(r'[\*\†\‡\§\¶]', '', line)
            cleaned = re.sub(r'\d+', '', cleaned)
            cleaned = cleaned.strip()
            
            name_matches = re.findall(r'[A-Z][a-z]+\s+[A-Z][a-z]+', cleaned)
            if name_matches:
                authors.extend(name_matches[:3])
                break
    
    if authors:
        if len(authors) > 3:
            return ', '.join(authors[:3]) + ' et al.'
        return ', '.join(authors)
    
    return "未提取"

def get_impact_factor(journal_name, impact_factors):
    """获取期刊影响因子"""
    return impact_factors.get(journal_name, 0.0)

def extract_eqe_comprehensive(text):
    """全面提取EQE"""
    values = []
    
    patterns = [
        r'EQE[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
        r'external quantum efficiency[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
        r'EQE[^0-9]*?[≥>]\s*([0-9]+\.?[0-9]*)\s*%',
        r'maximum EQE[^0-9]*?([0-9]+\.?[0-9]*)\s*%',
        r'peak EQE[^0-9]*?([0-9]+\.?[0-9]*)\s*%',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                v = float(m)
                if 0.1 < v < 80:
                    values.append(v)
            except:
                pass
    
    if values:
        return f"{max(values):.2f}%"
    return ""

def extract_cie_comprehensive(text):
    """全面提取CIE坐标"""
    patterns = [
        r'CIE[^0-9]*?\(([0-9]\.[0-9]+)\s*[,，]\s*([0-9]\.[0-9]+)\)',
        r'CIE[^0-9]*?([0-9]\.[0-9]+)\s*[,，]\s*([0-9]\.[0-9]+)',
        r'chromaticity[^0-9]*?\(([0-9]\.[0-9]+)\s*[,，]\s*([0-9]\.[0-9]+)\)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                x, y = float(m[0]), float(m[1])
                if 0 < x < 1 and 0 < y < 1:
                    return f"({x:.4f}, {y:.4f})"
            except:
                pass
    
    return ""

def extract_lifetime_comprehensive(text):
    """全面提取寿命"""
    values = []
    
    patterns = [
        r'T[⑤5]0[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hour|hours|小时)',
        r'LT[⑤5]0[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hour|hours)',
        r'lifetime[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hour|hours|小时)',
        r'operational[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hour|hours)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                v = float(m[0])
                if 1 < v < 50000:
                    values.append(v)
            except:
                pass
    
    if values:
        max_v = max(values)
        if max_v >= 1000:
            return f"{max_v:.0f} h ({max_v/1000:.2f}k h)"
        return f"{max_v:.1f} h"
    return ""

def extract_device_structure(text):
    """提取器件结构"""
    materials = []
    
    layer_keywords = {
        'ITO': r'\bITO\b',
        'PEDOT:PSS': r'PEDOT:PSS|PEDOT\s*:\s*PSS',
        'TFB': r'\bTFB\b',
        'PVK': r'\bPVK\b',
        'Poly-TPD': r'Poly-TPD|Poly\s*-\s*TPD',
        'QD层': r'quantum dot|QD|InP\.?QD|CdSe',
        'ZnO': r'\bZnO\b',
        'ZnMgO': r'ZnMgO|Zn\d*Mg\d*O',
        'TPBi': r'\bTPBi\b',
        'LiF': r'\bLiF\b',
        'Al': r'\bAl\b(?!.*\bGa\b)',
        'Ag': r'\bAg\b',
        'MoO3': r'MoO\d|MoO3',
        'NiO': r'\bNiO\b',
    }
    
    for mat, pattern in layer_keywords.items():
        if re.search(pattern, text, re.IGNORECASE):
            materials.append(mat)
    
    order = ['ITO', 'PEDOT:PSS', 'Poly-TPD', 'TFB', 'PVK', 'QD层', 'ZnO', 'ZnMgO', 'TPBi', 'LiF', 'Al', 'Ag', 'MoO3', 'NiO']
    
    ordered = []
    for mat in order:
        if mat in materials:
            ordered.append(mat)
    
    return ' / '.join(ordered) if ordered else ""

def extract_optimization(text):
    """提取优化信息"""
    text_lower = text.lower()
    
    levels = []
    level_keywords = {
        '材料合成': ['synthesis', 'material design', 'precursor'],
        '核壳结构': ['core-shell', 'core/shell', 'shell growth'],
        '表面处理': ['surface treatment', 'surface modification', 'passivation'],
        '配体工程': ['ligand engineering', 'ligand exchange', 'ligand modification'],
        '器件结构': ['device architecture', 'device structure', 'interface engineering'],
        '工艺优化': ['annealing', 'thermal treatment', 'solution processing'],
    }
    
    for level, keywords in level_keywords.items():
        if any(kw in text_lower for kw in keywords):
            levels.append(level)
    
    strategies = []
    strategy_keywords = {
        '表面钝化': ['passivation', 'defect passivation'],
        '配体交换': ['ligand exchange', 'ligand replacement'],
        '核壳工程': ['core-shell', 'shell growth'],
        '界面工程': ['interface engineering', 'interface modification'],
        '退火处理': ['annealing', 'thermal treatment'],
        '溶剂工程': ['solvent engineering', 'solvent treatment'],
        '元素掺杂': ['doping', 'doped', 'dopant'],
        '刻蚀策略': ['etching', 'core etching'],
    }
    
    for strategy, keywords in strategy_keywords.items():
        if any(kw in text_lower for kw in keywords):
            strategies.append(strategy)
    
    return '、'.join(levels), '、'.join(strategies)

def extract_supplementary(text):
    """提取补充信息"""
    info = []
    
    # 波长
    wl_patterns = [
        r'emission wavelength[^0-9]*?([0-9]{3})\s*nm',
        r'peak wavelength[^0-9]*?([0-9]{3})\s*nm',
        r'([0-9]{3})\s*nm[^0-9]*?(?:emission|PL|peak)',
    ]
    
    wavelengths = []
    for pattern in wl_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                wl = int(m)
                if 400 <= wl <= 800:
                    wavelengths.append(wl)
            except:
                pass
    
    if wavelengths:
        min_wl, max_wl = min(wavelengths), max(wavelengths)
        avg_wl = sum(wavelengths) / len(wavelengths)
        
        if 450 <= avg_wl < 495:
            color = "蓝光"
        elif 495 <= avg_wl < 570:
            color = "绿光"
        elif 570 <= avg_wl < 620:
            color = "黄光"
        elif 620 <= avg_wl <= 750:
            color = "红光"
        else:
            color = ""
        
        if min_wl == max_wl:
            info.append(f"发射波长: {min_wl} nm")
        else:
            info.append(f"发射波长: {min_wl}-{max_wl} nm")
        
        if color:
            info.append(f"颜色: {color}")
    
    # 亮度
    lum_patterns = [
        r'luminance[^0-9]*?([0-9,]+)\s*cd/m',
        r'brightness[^0-9]*?([0-9,]+)\s*cd/m',
    ]
    
    for pattern in lum_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                lum = int(matches[0].replace(',', ''))
                if lum > 100:
                    info.append(f"亮度: {lum:,} cd/m²")
                    break
            except:
                pass
    
    return '; '.join(info)

def analyze_pdf(pdf_path, impact_factors):
    """分析单个PDF文件"""
    print(f"\n分析: {pdf_path.name}")
    
    text = extract_full_text(pdf_path)
    if not text:
        return None
    
    # 提取所有信息
    title = extract_title(text, pdf_path.name)
    journal = extract_journal_info(text)
    authors = extract_authors(text)
    if_value = get_impact_factor(journal, impact_factors)
    device_structure = extract_device_structure(text)
    opt_level, opt_strategy = extract_optimization(text)
    eqe = extract_eqe_comprehensive(text)
    cie = extract_cie_comprehensive(text)
    lifetime = extract_lifetime_comprehensive(text)
    supp_info = extract_supplementary(text)
    
    print(f"  期刊: {journal} (IF: {if_value})")
    print(f"  EQE: {eqe}")
    print(f"  寿命: {lifetime}")
    
    return {
        'File': pdf_path.name,
        'URL': pdf_path.resolve().as_uri(),
        '期刊名称': journal,
        '影响因子': if_value,
        '作者': authors,
        '论文标题': title,
        '器件结构': device_structure,
        '优化层级': opt_level,
        '优化策略': opt_strategy,
        'EQE（外量子效率）': eqe,
        '色度坐标': cie,
        '寿命': lifetime,
        '补充信息': supp_info
    }

def create_excel_report(results, output_path):
    """创建Excel报告"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "论文分析结果"
    
    # 表头
    headers = ['File', 'URL', '期刊名称', '影响因子', '作者', '论文标题', '器件结构', 
               '优化层级', '优化策略', 'EQE（外量子效率）', '色度坐标', '寿命', '补充信息']
    
    # 样式
    header_fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11, name='Arial')
    cell_font = Font(size=10, name='Arial')
    thin_border = Border(
        left=Side(style='thin', color='BFBFBF'),
        right=Side(style='thin', color='BFBFBF'),
        top=Side(style='thin', color='BFBFBF'),
        bottom=Side(style='thin', color='BFBFBF')
    )
    
    # 写入表头
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border
    
    # 按影响因子排序
    results_sorted = sorted(results, key=lambda x: x['影响因子'] if x else 0, reverse=True)
    
    # 写入数据
    for row_idx, result in enumerate(results_sorted, 2):
        if result:
            for col_idx, header in enumerate(headers, 1):
                value = result.get(header, '')
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = cell_font
                cell.alignment = Alignment(vertical='top', wrap_text=True)
                cell.border = thin_border
                
                # 高亮有数据的单元格
                if col_idx in [10, 11, 12] and value:
                    cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    
    # 设置列宽
    column_widths = [30, 45, 25, 12, 30, 55, 45, 30, 35, 18, 22, 22, 40]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    
    # 设置行高
    ws.row_dimensions[1].height = 35
    for row in range(2, len(results) + 2):
        ws.row_dimensions[row].height = 80
    
    # 冻结首行
    ws.freeze_panes = 'A2'
    
    # 保存
    wb.save(output_path)
    print(f"\n✓ Excel报告已保存: {output_path}")

def main():
    """主函数"""
    args = parse_args()
    pdf_dir = args.pdf_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    journal_config_path = args.journal_config.expanduser().resolve()
    use_existing_json = USE_EXISTING_JSON and not args.no_json
    impact_factors = load_journal_impact_factors(
        journal_config_path,
        use_existing_json=use_existing_json,
    )

    print("="*70)
    print(" PDF论文分析工具 v1.1")
    print("="*70)
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取PDF文件
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    print(f"\n找到 {len(pdf_files)} 个PDF文件")
    
    if not pdf_files:
        print("\n错误: 未找到PDF文件！")
        print(f"请将PDF文件放入: {pdf_dir}")
        return
    
    # 分析每个PDF
    results = []
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}]", end='')
        result = analyze_pdf(pdf_file, impact_factors)
        if result:
            results.append(result)
    
    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"论文分析报告_{timestamp}.xlsx"
    
    create_excel_report(results, output_file)
    
    # 统计
    eqe_count = sum(1 for r in results if r['EQE（外量子效率）'])
    lifetime_count = sum(1 for r in results if r['寿命'])
    cie_count = sum(1 for r in results if r['色度坐标'])
    
    print(f"\n{'='*70}")
    print(" 分析完成!")
    print(f"{'='*70}")
    print(f" 总文件数: {len(results)}")
    print(f" EQE数据: {eqe_count}/{len(results)}")
    print(f" 寿命数据: {lifetime_count}/{len(results)}")
    print(f" CIE坐标: {cie_count}/{len(results)}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
