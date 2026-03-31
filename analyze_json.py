#!/usr/bin/env python3
import json

# 读取JSON文件
with open('/Users/locybe/论文处理/论文文件2/3.1抽样5篇/输出结果_3.1x重跑/论文分析报告_20260316_181819.json', 'r') as f:
    papers = json.load(f)

total_devices = 0
noisy_notes_devices = 0
noise_examples = []
data_source_stats = {
    'eqe_source': 0,
    'cie_source': 0,
    'lifetime_source': 0,
    'structure_source': 0,
    'total_papers_with_devices': 0
}

print("=" * 80)
print("论文分析报告 - 详细分析")
print("=" * 80)

for i, paper in enumerate(papers):
    print(f"\n{'=' * 80}")
    print(f"论文 {i+1}: {paper['File']}")
    print(f"标题: {paper['paper_info']['title']}")
    print(f"期刊: {paper['paper_info']['journal_name']}")
    print(f"处理状态: {paper['processing_status']}")
    print(f"{'=' * 80}")
    
    # 统计data_source字段完整性
    has_any_devices = len(paper['devices']) > 0
    if has_any_devices:
        data_source_stats['total_papers_with_devices'] += 1
        if paper['data_source']['eqe_source']:
            data_source_stats['eqe_source'] += 1
        if paper['data_source']['cie_source']:
            data_source_stats['cie_source'] += 1
        if paper['data_source']['lifetime_source']:
            data_source_stats['lifetime_source'] += 1
        if paper['data_source']['structure_source']:
            data_source_stats['structure_source'] += 1
    
    # 检查器件
    if paper['devices']:
        print(f"\n器件数量: {len(paper['devices'])}")
        total_devices += len(paper['devices'])
        
        for j, device in enumerate(paper['devices']):
            notes = device.get('notes', '')
            is_noisy = False
            
            # 检测噪声特征
            noise_indicators = [
                'www.', 
                'journal', 
                'Figure', 
                'RESEARCH ARTICLE', 
                'authors', 
                'corresponding',
                'components of',
                'as shown in Fig',
                'TA kinetic traces',
                'trap state',
                'as a result, we achieve'
            ]
            
            for indicator in noise_indicators:
                if indicator.lower() in str(notes).lower():
                    is_noisy = True
                    break
            
            if is_noisy:
                noisy_notes_devices += 1
                noise_examples.append({
                    'paper': paper['File'],
                    'device_index': j,
                    'device_label': device.get('device_label'),
                    'notes': notes[:300]
                })
            
            print(f"\n  器件 {j+1}:")
            print(f"    Label: {device.get('device_label')}")
            print(f"    Structure: {device.get('structure')}")
            print(f"    EQE: {device.get('eqe')}")
            print(f"    CIE: {device.get('cie')}")
            print(f"    Lifetime: {device.get('lifetime')}")
            print(f"    Luminance: {device.get('luminance')}")
            print(f"    Notes (前200字符): {str(notes)[:200]}...")
            print(f"    噪声文本: {'是' if is_noisy else '否'}")
    else:
        print("\n无器件数据")
    
    # 打印data_source情况
    print(f"\nData Source 字段完整性:")
    print(f"  eqe_source: {'有' if paper['data_source']['eqe_source'] else '无'}")
    print(f"  cie_source: {'有' if paper['data_source']['cie_source'] else '无'}")
    print(f"  lifetime_source: {'有' if paper['data_source']['lifetime_source'] else '无'}")
    print(f"  structure_source: {'有' if paper['data_source']['structure_source'] else '无'}")

# 打印汇总统计
print(f"\n{'=' * 80}")
print("汇总统计")
print(f"{'=' * 80}")
print(f"总论文数: {len(papers)}")
print(f"包含器件的论文数: {data_source_stats['total_papers_with_devices']}")
print(f"总器件数: {total_devices}")
print(f"包含噪声文本的器件数: {noisy_notes_devices}")
print(f"噪声器件比例: {noisy_notes_devices / total_devices * 100:.1f}%" if total_devices > 0 else "无数据")

print(f"\nData Source 字段缺失统计 (针对有器件的论文):")
total_papers = data_source_stats['total_papers_with_devices']
print(f"  eqe_source: 缺失 {total_papers - data_source_stats['eqe_source']}/{total_papers}")
print(f"  cie_source: 缺失 {total_papers - data_source_stats['cie_source']}/{total_papers}")
print(f"  lifetime_source: 缺失 {total_papers - data_source_stats['lifetime_source']}/{total_papers}")
print(f"  structure_source: 缺失 {total_papers - data_source_stats['structure_source']}/{total_papers}")

print(f"\n噪声文本示例:")
for ex in noise_examples:
    print(f"\n论文: {ex['paper']}")
    print(f"器件索引: {ex['device_index'] + 1}")
    print(f"器件标签: {ex['device_label']}")
    print(f"Notes: {ex['notes']}")
