"""
章节过滤器 v3.1

使用 Markdown 结构感知 + 块级打分 + 邻域窗口保留来压缩输入上下文，
同时尽量保留设备结构、性能参数、表格和图注等高价值信息。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SectionMatch:
    """兼容旧版的章节匹配结构。"""

    title: str
    start_pos: int
    end_pos: int
    content: str
    is_noise: bool = False


@dataclass
class MarkdownBlock:
    """Markdown 块。"""

    index: int
    block_type: str
    text: str
    heading_path: List[str] = field(default_factory=list)
    heading_level: int = 0
    score: float = 0.0
    keep: bool = False
    anchor_id: Optional[str] = None


@dataclass
class TableAnchor:
    """带锚点的表格上下文。"""

    anchor_id: str
    text: str
    heading_path: List[str] = field(default_factory=list)
    prev_text: str = ""
    next_text: str = ""


@dataclass
class CleanedContent:
    """清洗后的内容结构。"""

    abstract: str = ""
    introduction: str = ""
    experimental: str = ""
    results: str = ""
    discussion: str = ""
    conclusion: str = ""

    other_sections: Dict[str, str] = field(default_factory=dict)
    tables: List[str] = field(default_factory=list)
    anchored_tables: List[str] = field(default_factory=list)
    blocks: List[MarkdownBlock] = field(default_factory=list)
    kept_block_indices: List[int] = field(default_factory=list)

    original_length: int = 0
    cleaned_length: int = 0
    removed_sections: List[str] = field(default_factory=list)
    full_text: str = ""
    condensed_text: str = ""

    @property
    def reduction_ratio(self) -> float:
        if self.original_length == 0:
            return 0.0
        return 1 - (self.cleaned_length / self.original_length)

    def get_text_for_extraction(self) -> str:
        if self.condensed_text:
            return self.condensed_text

        parts: List[str] = []
        if self.experimental:
            parts.append("## Experimental Section\n\n" + self.experimental)
        if self.results:
            parts.append("## Results\n\n" + self.results)
        if self.abstract:
            parts.append("## Abstract\n\n" + self.abstract)
        if self.discussion:
            parts.append("## Discussion\n\n" + self.discussion)
        if self.introduction:
            parts.append("## Introduction\n\n" + self.introduction)
        if self.conclusion:
            parts.append("## Conclusion\n\n" + self.conclusion)
        if self.tables:
            parts.append("## Tables\n")
            parts.extend(self.tables)
        if not parts and self.full_text:
            return self.full_text
        return "\n\n".join(parts)


class SectionFilter:
    """Markdown 结构感知过滤器。"""

    NOISE_PATTERNS = [
        r"references?",
        r"bibliography",
        r"文献",
        r"acknowledg?ments?",
        r"致谢",
        r"资金资助",
        r"author\s*contributions?",
        r"作者贡献",
        r"supplementary\s*(material|information|data)",
        r"补充材料",
        r"支持信息",
        r"conflict\s*of\s*interest",
        r"利益冲突",
        r"data\s*availability",
        r"数据可用性",
        r"author\s*information",
        r"corresponding\s*author",
        r"通讯作者",
        r"appendix",
        r"appendices",
        r"附录",
    ]

    CORE_PATTERNS = {
        "abstract": [r"abstract", r"摘要"],
        "introduction": [r"introduction", r"引言", r"background", r"背景"],
        "experimental": [
            r"experimental\s*(section|methods?|procedures?)?",
            r"materials?\s*and\s*methods?",
            r"实验(部分|方法)?",
            r"材料与方法",
            r"methodology",
        ],
        "results": [r"results?(\s*and\s*discussion)?", r"结果(与讨论)?"],
        "discussion": [r"discussion", r"讨论"],
        "conclusion": [r"conclusions?", r"结论", r"summary", r"总结"],
    }

    PARAMETER_KEYWORDS = [
        "eqe",
        "external quantum efficiency",
        "cie",
        "luminance",
        "current efficiency",
        "power efficiency",
        "efficiency",
        "lifetime",
        "lt50",
        "t50",
        "t90",
        "turn-on voltage",
        "cd/a",
        "lm/w",
        "cd/m2",
        "cd/m²",
        "ma/cm2",
        "ma/cm²",
    ]

    STRUCTURE_KEYWORDS = [
        "device",
        "devices",
        "structure",
        "architecture",
        "ito",
        "fto",
        "pedot",
        "pedot:pss",
        "htl",
        "etl",
        "eml",
        "host",
        "dopant",
        "layer",
        "spin-coating",
        "spin coating",
        "vacuum deposition",
    ]

    PRIORITY_HEADINGS = [
        "abstract",
        "experimental",
        "method",
        "results",
        "discussion",
        "device",
        "performance",
        "characterization",
        "figure",
        "table",
    ]

    NOISY_CONTEXT_HEADINGS = [
        "introduction",
        "background",
        "related work",
        "literature review",
    ]

    FIGURE_CAPTION_PATTERN = re.compile(r"^(figure|fig\.?|scheme|图|表)\s*\d+", re.IGNORECASE)
    LIST_PATTERN = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")
    TABLE_SEPARATOR_PATTERN = re.compile(r"^\|?\s*[:\-]+(?:\s*\|\s*[:\-]+)+\s*\|?$")

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.window_size = max(0, int(self.config.get("block_window", 1)))
        self.max_input_chars = max(4000, int(self.config.get("max_input_chars", 24000)))
        self.max_blocks = max(10, int(self.config.get("max_blocks", 80)))
        self.min_block_score = float(self.config.get("min_block_score", 3.0))
        self.keep_table_context = bool(self.config.get("keep_table_context", True))

        custom_remove = self.config.get("remove_sections", [])
        custom_keep = self.config.get("keep_sections", [])
        custom_parameter_keywords = self.config.get("parameter_keywords", [])
        custom_structure_keywords = self.config.get("structure_keywords", [])

        self.parameter_keywords = sorted(
            {keyword.lower() for keyword in self.PARAMETER_KEYWORDS + custom_parameter_keywords},
            key=len,
            reverse=True,
        )
        self.structure_keywords = sorted(
            {keyword.lower() for keyword in self.STRUCTURE_KEYWORDS + custom_structure_keywords},
            key=len,
            reverse=True,
        )

        self._noise_regex = self._build_regex(self.NOISE_PATTERNS + custom_remove)
        self._core_regexes: Dict[str, re.Pattern[str]] = {}
        for section_name, patterns in self.CORE_PATTERNS.items():
            merged_patterns = patterns + [p for p in custom_keep if p not in patterns]
            self._core_regexes[section_name] = self._build_regex(merged_patterns)

        self._metric_regexes = [
            re.compile(r"\b\d+(?:\.\d+)?\s?%\b", re.IGNORECASE),
            re.compile(r"\b\d+(?:\.\d+)?\s?cd/A\b", re.IGNORECASE),
            re.compile(r"\b\d+(?:\.\d+)?\s?lm/W\b", re.IGNORECASE),
            re.compile(r"\b\d+(?:\.\d+)?\s?cd/m(?:²|2)\b", re.IGNORECASE),
            re.compile(r"\b\d+(?:\.\d+)?\s?mA/cm(?:²|2)\b", re.IGNORECASE),
            re.compile(r"\b\d+(?:\.\d+)?\s?V\b", re.IGNORECASE),
            re.compile(r"\(\s*0?\.\d+\s*,\s*0?\.\d+\s*\)"),
            re.compile(r"\b(?:LT|T)\s?(?:50|90)\s*=\s*\d+(?:\.\d+)?\s?h\b", re.IGNORECASE),
        ]

    def _build_regex(self, patterns: List[str]) -> re.Pattern[str]:
        combined = "|".join(f"({pattern})" for pattern in patterns)
        return re.compile(combined, re.IGNORECASE)

    def clean(self, markdown: str) -> CleanedContent:
        result = CleanedContent(original_length=len(markdown))
        if not self.enabled:
            result.full_text = markdown
            result.cleaned_length = len(markdown)
            result.condensed_text = markdown
            return result

        stripped_markdown, removed_titles = self._strip_tail_noise(markdown)
        result.removed_sections.extend(removed_titles)

        raw_blocks = self._split_markdown_blocks(stripped_markdown)
        anchored_blocks, table_anchors = self._anchor_tables(raw_blocks)
        self._score_blocks(anchored_blocks)
        kept_indices = self._select_kept_blocks(anchored_blocks)
        condensed_text = self._compose_condensed_markdown(anchored_blocks, table_anchors, kept_indices)

        result.blocks = anchored_blocks
        result.tables = [anchor.text for anchor in table_anchors]
        result.anchored_tables = [self._format_table_anchor(anchor) for anchor in table_anchors]
        result.kept_block_indices = sorted(kept_indices)
        result.condensed_text = condensed_text
        result.full_text = condensed_text or stripped_markdown
        result.cleaned_length = len(result.full_text)

        self._populate_legacy_sections(result, raw_blocks)
        return result

    def _strip_tail_noise(self, markdown: str) -> Tuple[str, List[str]]:
        lines = markdown.splitlines()
        headings: List[Tuple[int, str]] = []
        for idx, line in enumerate(lines):
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if match:
                headings.append((idx, match.group(2).strip()))

        cutoff_line: Optional[int] = None
        removed_titles: List[str] = []
        found_noise = False
        for line_index, title in reversed(headings):
            if self._is_noise_section(title):
                cutoff_line = line_index
                removed_titles.append(title)
                found_noise = True
                continue
            if found_noise:
                break

        if cutoff_line is None:
            return markdown, []

        return "\n".join(lines[:cutoff_line]).strip(), list(reversed(removed_titles))

    def _split_markdown_blocks(self, markdown: str) -> List[MarkdownBlock]:
        lines = markdown.splitlines()
        blocks: List[MarkdownBlock] = []
        heading_stack: List[Tuple[int, str]] = []
        buffer: List[str] = []
        buffer_type = "paragraph"

        def current_path() -> List[str]:
            return [title for _, title in heading_stack]

        def flush_buffer() -> None:
            nonlocal buffer, buffer_type
            text = "\n".join(buffer).strip()
            if text:
                blocks.append(
                    MarkdownBlock(
                        index=len(blocks),
                        block_type=buffer_type,
                        text=text,
                        heading_path=current_path(),
                    )
                )
            buffer = []
            buffer_type = "paragraph"

        idx = 0
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()

            heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading_match:
                flush_buffer()
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                blocks.append(
                    MarkdownBlock(
                        index=len(blocks),
                        block_type="heading",
                        text=f"{'#' * level} {title}",
                        heading_path=current_path(),
                        heading_level=level,
                    )
                )
                idx += 1
                continue

            if not stripped:
                flush_buffer()
                idx += 1
                continue

            if self._is_table_start(lines, idx):
                flush_buffer()
                table_lines = [lines[idx].rstrip()]
                idx += 1
                while idx < len(lines):
                    candidate = lines[idx].rstrip()
                    if not candidate.strip() or candidate.lstrip().startswith("#"):
                        break
                    if "|" not in candidate:
                        break
                    table_lines.append(candidate)
                    idx += 1
                blocks.append(
                    MarkdownBlock(
                        index=len(blocks),
                        block_type="table",
                        text="\n".join(table_lines).strip(),
                        heading_path=current_path(),
                    )
                )
                continue

            if self.FIGURE_CAPTION_PATTERN.match(stripped):
                flush_buffer()
                caption_lines = [stripped]
                idx += 1
                while idx < len(lines) and lines[idx].strip() and not re.match(r"^(#{1,6})\s+", lines[idx]):
                    if self._is_table_start(lines, idx):
                        break
                    caption_lines.append(lines[idx].strip())
                    idx += 1
                blocks.append(
                    MarkdownBlock(
                        index=len(blocks),
                        block_type="figure_caption",
                        text="\n".join(caption_lines),
                        heading_path=current_path(),
                    )
                )
                continue

            if self.LIST_PATTERN.match(stripped):
                flush_buffer()
                list_lines = [stripped]
                idx += 1
                while idx < len(lines):
                    candidate = lines[idx].strip()
                    if not candidate or re.match(r"^(#{1,6})\s+", lines[idx]) or self._is_table_start(lines, idx):
                        break
                    if not self.LIST_PATTERN.match(candidate):
                        break
                    list_lines.append(candidate)
                    idx += 1
                blocks.append(
                    MarkdownBlock(
                        index=len(blocks),
                        block_type="list",
                        text="\n".join(list_lines),
                        heading_path=current_path(),
                    )
                )
                continue

            buffer_type = "paragraph"
            buffer.append(stripped)
            idx += 1

        flush_buffer()
        return blocks

    def _is_table_start(self, lines: List[str], index: int) -> bool:
        if index + 1 >= len(lines):
            return False
        current = lines[index].strip()
        separator = lines[index + 1].strip()
        return current.startswith("|") and self.TABLE_SEPARATOR_PATTERN.match(separator) is not None

    def _anchor_tables(self, blocks: List[MarkdownBlock]) -> Tuple[List[MarkdownBlock], List[TableAnchor]]:
        anchored_blocks: List[MarkdownBlock] = []
        table_anchors: List[TableAnchor] = []

        for block in blocks:
            if block.block_type != "table":
                anchored_blocks.append(
                    MarkdownBlock(
                        index=len(anchored_blocks),
                        block_type=block.block_type,
                        text=block.text,
                        heading_path=list(block.heading_path),
                        heading_level=block.heading_level,
                    )
                )
                continue

            anchor_id = f"TABLE_{len(table_anchors) + 1:04d}"
            prev_text = self._find_neighbor_text(blocks, block.index, direction=-1)
            next_text = self._find_neighbor_text(blocks, block.index, direction=1)
            table_anchors.append(
                TableAnchor(
                    anchor_id=anchor_id,
                    text=block.text,
                    heading_path=list(block.heading_path),
                    prev_text=prev_text,
                    next_text=next_text,
                )
            )
            anchored_blocks.append(
                MarkdownBlock(
                    index=len(anchored_blocks),
                    block_type="table_anchor",
                    text=f"[{anchor_id}]",
                    heading_path=list(block.heading_path),
                    anchor_id=anchor_id,
                )
            )

        return anchored_blocks, table_anchors

    def _find_neighbor_text(self, blocks: List[MarkdownBlock], index: int, direction: int) -> str:
        cursor = index + direction
        while 0 <= cursor < len(blocks):
            block = blocks[cursor]
            if block.block_type in {"paragraph", "list", "figure_caption"} and block.text.strip():
                return block.text.strip()
            cursor += direction
        return ""

    def _score_blocks(self, blocks: List[MarkdownBlock]) -> None:
        for block in blocks:
            if block.block_type == "table_anchor":
                block.score = 100.0
                continue

            lower_text = block.text.lower()
            heading_context = " ".join(block.heading_path).lower()
            parameter_hits = sum(1 for keyword in self.parameter_keywords if keyword in lower_text)
            structure_hits = sum(1 for keyword in self.structure_keywords if keyword in lower_text)
            metric_hits = sum(1 for pattern in self._metric_regexes if pattern.search(block.text))
            has_numeric = bool(re.search(r"\d", block.text))

            heading_bonus = 0.0
            if any(term in heading_context for term in self.PRIORITY_HEADINGS):
                heading_bonus += 1.8
            if block.block_type == "heading":
                title = block.heading_path[-1].lower() if block.heading_path else lower_text
                if any(term in title for term in self.PRIORITY_HEADINGS):
                    heading_bonus += 1.2

            caption_bonus = 2.0 if block.block_type == "figure_caption" else 0.0
            list_bonus = 0.4 if block.block_type == "list" else 0.0
            co_occurrence_bonus = 1.5 if has_numeric and (parameter_hits or structure_hits) else 0.0

            noise_penalty = 0.0
            if any(term in heading_context for term in self.NOISY_CONTEXT_HEADINGS):
                noise_penalty += 1.0
            if self._is_noise_section(block.heading_path[-1] if block.heading_path else block.text):
                noise_penalty += 6.0

            block.score = (
                2.5 * parameter_hits
                + 2.0 * structure_hits
                + 3.0 * metric_hits
                + heading_bonus
                + caption_bonus
                + list_bonus
                + co_occurrence_bonus
                - noise_penalty
            )

    def _select_kept_blocks(self, blocks: List[MarkdownBlock]) -> List[int]:
        seed_indices: set[int] = set()
        mandatory_indices: set[int] = set()

        for block in blocks:
            if self._is_noise_section(block.heading_path[-1] if block.heading_path else block.text):
                continue
            if block.block_type == "table_anchor":
                seed_indices.add(block.index)
                mandatory_indices.add(block.index)
                continue
            if block.score >= self.min_block_score:
                seed_indices.add(block.index)
                if block.score >= self.min_block_score + 2.0:
                    mandatory_indices.add(block.index)

        kept_indices: set[int] = set()
        for seed in seed_indices:
            start = max(0, seed - self.window_size)
            end = min(len(blocks) - 1, seed + self.window_size)
            for idx in range(start, end + 1):
                if self._is_noise_section(blocks[idx].heading_path[-1] if blocks[idx].heading_path else blocks[idx].text):
                    continue
                kept_indices.add(idx)
            kept_indices.update(self._collect_heading_context(blocks, seed))
            if self.keep_table_context and blocks[seed].block_type == "table_anchor":
                if seed - 1 >= 0:
                    kept_indices.add(seed - 1)
                if seed + 1 < len(blocks):
                    kept_indices.add(seed + 1)
                    mandatory_indices.add(seed + 1)
                if seed - 1 >= 0:
                    mandatory_indices.add(seed - 1)

        if not kept_indices:
            return list(range(min(len(blocks), self.max_blocks)))

        kept_indices.update(mandatory_indices)
        kept_list = sorted(kept_indices)

        def total_chars(indices: List[int]) -> int:
            return sum(len(blocks[idx].text) + 2 for idx in indices)

        optional = [
            idx
            for idx in kept_list
            if idx not in mandatory_indices and blocks[idx].block_type not in {"heading", "table_anchor"}
        ]
        optional.sort(key=lambda idx: (blocks[idx].score, len(blocks[idx].text), idx))

        while (len(kept_list) > self.max_blocks or total_chars(kept_list) > self.max_input_chars) and optional:
            drop_idx = optional.pop(0)
            kept_indices.discard(drop_idx)
            kept_list = sorted(kept_indices)

        return kept_list

    def _collect_heading_context(self, blocks: List[MarkdownBlock], index: int) -> set[int]:
        context: set[int] = set()
        current_path = blocks[index].heading_path
        if not current_path:
            return context

        needed = set(current_path)
        for cursor in range(index - 1, -1, -1):
            block = blocks[cursor]
            if block.block_type != "heading":
                continue
            title = block.heading_path[-1] if block.heading_path else ""
            if title in needed:
                context.add(cursor)
                needed.discard(title)
            if not needed:
                break
        return context

    def _compose_condensed_markdown(
        self,
        blocks: List[MarkdownBlock],
        table_anchors: List[TableAnchor],
        kept_indices: List[int],
    ) -> str:
        kept_index_set = set(kept_indices)
        for block in blocks:
            block.keep = block.index in kept_index_set

        body_parts = [blocks[idx].text for idx in kept_indices if blocks[idx].text.strip()]
        table_parts = [self._format_table_anchor(anchor) for anchor in table_anchors]

        parts: List[str] = []
        if table_parts:
            parts.append("## Anchored Tables\n\n" + "\n\n".join(table_parts))
        if body_parts:
            parts.append("## Condensed Context\n\n" + "\n\n".join(body_parts))

        condensed = "\n\n".join(part for part in parts if part).strip()
        if len(condensed) <= self.max_input_chars:
            return condensed
        return condensed[: self.max_input_chars].rsplit("\n\n", 1)[0].strip()

    def _format_table_anchor(self, anchor: TableAnchor) -> str:
        lines = [f"### [{anchor.anchor_id}]"]
        if anchor.heading_path:
            lines.append("Section: " + " > ".join(anchor.heading_path))
        if anchor.prev_text:
            lines.append("Context before:\n" + anchor.prev_text)
        lines.append("Table:\n" + anchor.text)
        if anchor.next_text:
            lines.append("Context after:\n" + anchor.next_text)
        return "\n\n".join(lines)

    def _populate_legacy_sections(self, result: CleanedContent, blocks: List[MarkdownBlock]) -> None:
        section_buffers: Dict[str, List[str]] = {name: [] for name in self.CORE_PATTERNS}

        for block in blocks:
            if block.block_type in {"heading", "table"}:
                continue
            title = block.heading_path[0] if block.heading_path else ""
            section_type = self._identify_section_type(title)
            if section_type:
                section_buffers[section_type].append(block.text)
            elif title:
                existing = result.other_sections.get(title, "")
                joined = (existing + "\n\n" + block.text).strip() if existing else block.text
                result.other_sections[title] = joined

        result.abstract = "\n\n".join(section_buffers["abstract"]).strip()
        result.introduction = "\n\n".join(section_buffers["introduction"]).strip()
        result.experimental = "\n\n".join(section_buffers["experimental"]).strip()
        result.results = "\n\n".join(section_buffers["results"]).strip()
        result.discussion = "\n\n".join(section_buffers["discussion"]).strip()
        result.conclusion = "\n\n".join(section_buffers["conclusion"]).strip()

    def _parse_sections(self, markdown: str) -> List[Dict[str, str]]:
        sections = []
        lines = markdown.split("\n")
        current_title = ""
        current_content: List[str] = []
        in_section = False

        for line in lines:
            header_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if header_match:
                if in_section and current_title:
                    sections.append({"title": current_title, "content": "\n".join(current_content).strip()})
                current_title = header_match.group(2).strip()
                current_content = []
                in_section = True
            elif in_section:
                current_content.append(line)

        if in_section and current_title:
            sections.append({"title": current_title, "content": "\n".join(current_content).strip()})
        if not sections:
            sections.append({"title": "Document", "content": markdown})
        return sections

    def _is_noise_section(self, title: str) -> bool:
        return bool(title and self._noise_regex.search(title))

    def _identify_section_type(self, title: str) -> Optional[str]:
        for section_type, regex in self._core_regexes.items():
            if title and regex.search(title):
                return section_type
        return None

    def _extract_tables(self, markdown: str) -> Tuple[str, List[str]]:
        tables = []
        table_pattern = re.compile(r"(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)", re.MULTILINE)
        for match in table_pattern.finditer(markdown):
            tables.append(match.group(1).strip())
        return table_pattern.sub("\n[TABLE]\n", markdown), tables

    def get_section_priority(self, section_type: str) -> int:
        priorities = {
            "experimental": 1,
            "results": 2,
            "abstract": 3,
            "discussion": 4,
            "introduction": 5,
            "conclusion": 6,
        }
        return priorities.get(section_type, 10)



def clean_paper_content(markdown: str, config: Optional[Dict[str, Any]] = None) -> CleanedContent:
    filter_instance = SectionFilter(config)
    return filter_instance.clean(markdown)
