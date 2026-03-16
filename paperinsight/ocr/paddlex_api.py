"""
PaddleX API 模块
功能: 百度AI Studio PaddleX 异步服务化部署 API 调用
文档: https://ai.baidu.com/ai-doc/AISTUDIO/fml7mozw5
"""

import base64
import json
import time
from pathlib import Path
from typing import Optional, Tuple, Union

import requests

from paperinsight.ocr.base import BaseOCR


class PaddleXAPI(BaseOCR):
    """百度AI Studio PaddleX API 客户端 (异步模式)"""

    JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"

    SUPPORTED_MODELS = {
        "layout": ["PaddleOCR-VL-1.5", "PaddleOCR-VL", "PP-StructureV3"],
        "ocr": ["PP-OCRv5"],
    }

    def __init__(
        self,
        api_key: str,
        model: str = "PaddleOCR-VL-1.5",
        timeout: int = 300,
        poll_interval: int = 5,
        max_retries: int = 3,
        use_doc_orientation: bool = False,
        use_doc_unwarping: bool = False,
        use_layout_detection: bool = True,
        use_chart_recognition: bool = False,
    ):
        """
        初始化 PaddleX API 客户端

        Args:
            api_key: AI Studio 访问令牌 (从 https://aistudio.baidu.com/paddleocr/task 获取)
            model: 使用的模型名称
            timeout: 请求超时时间(秒)
            poll_interval: 轮询间隔(秒)
            max_retries: 最大重试次数
            use_doc_orientation: 是否启用文档方向矫正
            use_doc_unwarping: 是否启用文档扭曲矫正
            use_layout_detection: 是否启用版面区域检测
            use_chart_recognition: 是否启用图表识别
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.use_doc_orientation = use_doc_orientation
        self.use_doc_unwarping = use_doc_unwarping
        self.use_layout_detection = use_layout_detection
        self.use_chart_recognition = use_chart_recognition

    def _get_headers(self) -> dict:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept-Encoding": "gzip, deflate, br",
        }

    def _encode_file(self, file_path: Union[str, Path]) -> bytes:
        """读取文件二进制内容"""
        with open(file_path, "rb") as f:
            return f.read()

    def _submit_job(self, file_path: Union[str, Path]) -> str:
        """
        提交解析任务

        Returns:
            job_id: 任务ID
        """
        file_path = Path(file_path)
        file_data = self._encode_file(file_path)

        optional_payload = {
            "useDocOrientationClassify": self.use_doc_orientation,
            "useDocUnwarping": self.use_doc_unwarping,
            "useChartRecognition": self.use_chart_recognition,
        }

        if self.model in self.SUPPORTED_MODELS["layout"]:
            optional_payload["useLayoutDetection"] = self.use_layout_detection

        data = {
            "model": self.model,
            "optionalPayload": json.dumps(optional_payload),
        }

        files = {
            "file": (file_path.name, file_data, "application/pdf"),
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.JOB_URL,
                    headers=self._get_headers(),
                    data=data,
                    files=files,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("code") == 0:
                        return result["data"]["jobId"]
                    else:
                        raise RuntimeError(f"提交任务失败: {result.get('msg', 'Unknown error')}")
                elif response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        time.sleep(10 * (attempt + 1))
                        continue
                    raise RuntimeError("PaddleX API 超出每日页数上限 (429)")
                else:
                    raise RuntimeError(f"提交任务失败 HTTP {response.status_code}: {response.text}")

            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"PaddleX API 请求失败: {e}")

        raise RuntimeError("PaddleX API 提交任务失败")

    def _poll_job_result(self, job_id: str) -> dict:
        """
        轮询任务结果

        Returns:
            解析结果
        """
        poll_url = f"{self.JOB_URL}/{job_id}"

        start_time = time.time()
        max_wait_time = 600

        while True:
            if time.time() - start_time > max_wait_time:
                raise RuntimeError("PaddleX API 任务轮询超时")

            try:
                response = requests.get(
                    poll_url,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )

                if response.status_code != 200:
                    raise RuntimeError(f"获取任务结果失败 HTTP {response.status_code}")

                result = response.json()
                if result.get("code") != 0:
                    raise RuntimeError(f"任务处理失败: {result.get('msg', 'Unknown error')}")

                state = result["data"]["state"]

                if state == "done":
                    return result["data"]
                elif state == "failed":
                    error_msg = result["data"].get("errorMsg", "Unknown error")
                    raise RuntimeError(f"PaddleX 任务失败: {error_msg}")
                elif state == "running":
                    try:
                        progress = result["data"].get("extractProgress", {})
                        total = progress.get("totalPages", "?")
                        extracted = progress.get("extractedPages", "?")
                        print(f"[PaddleX] 解析中... 已处理 {extracted}/{total} 页")
                    except Exception:
                        print("[PaddleX] 解析中...")
                elif state == "pending":
                    print("[PaddleX] 任务排队中...")

                time.sleep(self.poll_interval)

            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"PaddleX API 轮询失败: {e}")

    def _get_result_json(self, result_url: str) -> list:
        """从结果URL获取JSON结果"""
        response = requests.get(result_url, timeout=self.timeout)
        response.raise_for_status()

        lines = response.text.strip().split("\n")
        results = []
        for line in lines:
            line = line.strip()
            if line:
                results.append(json.loads(line))
        return results

    def extract_text_from_pdf(
        self,
        pdf_path: Union[str, Path],
        max_pages: Optional[int] = None,
    ) -> Tuple[str, str, dict]:
        """
        从 PDF 提取文本(使用异步版面解析 API)

        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大读取页数

        Returns:
            (full_text, front_text, metadata)
        """
        pdf_path = Path(pdf_path)

        try:
            print(f"[PaddleX] 提交任务: {pdf_path.name}")
            job_id = self._submit_job(pdf_path)
            print(f"[PaddleX] 任务ID: {job_id}, 等待结果...")

            job_result = self._poll_job_result(job_id)

            result_url = job_result["resultUrl"]["jsonUrl"]
            json_results = self._get_result_json(result_url)

            full_text_parts = []
            front_text = ""
            total_pages = 0

            for page_result in json_results:
                result_data = page_result.get("result", {})

                if self.model in self.SUPPORTED_MODELS["layout"]:
                    layout_results = result_data.get("layoutParsingResults", [])
                    for idx, page in enumerate(layout_results):
                        if max_pages is not None and total_pages >= max_pages:
                            break

                        markdown_obj = page.get("markdown", {})
                        page_text = markdown_obj.get("text", "")

                        if page_text:
                            full_text_parts.append(page_text)
                            if not front_text:
                                front_text = page_text
                        total_pages += 1
                else:
                    ocr_results = result_data.get("ocrResults", [])
                    for page in ocr_results:
                        if max_pages is not None and total_pages >= max_pages:
                            break

                        pruned_result = page.get("prunedResult", [])
                        page_texts = [item.get("text", "") for item in pruned_result if item.get("text")]
                        page_text = "\n".join(page_texts)

                        if page_text:
                            full_text_parts.append(page_text)
                            if not front_text:
                                front_text = page_text
                        total_pages += 1

            full_text = "\n\n".join(full_text_parts)
            metadata = {
                "pages": total_pages,
                "service": "PaddleX Async API",
                "model": self.model,
                "job_id": job_id,
            }

            print(f"[PaddleX] 完成, 共提取 {total_pages} 页")
            return full_text, front_text, metadata

        except Exception as e:
            print(f"[PaddleX] PDF 处理失败: {e}")
            return "", "", {}

    def extract_text_from_image(
        self,
        image_path: Union[str, Path],
    ) -> str:
        """
        从图片提取文本

        Args:
            image_path: 图片文件路径

        Returns:
            提取的文本
        """
        image_path = Path(image_path)

        try:
            print(f"[PaddleX] 提交图片任务: {image_path.name}")
            job_id = self._submit_job(image_path)
            print(f"[PaddleX] 任务ID: {job_id}, 等待结果...")

            job_result = self._poll_job_result(job_id)

            result_url = job_result["resultUrl"]["jsonUrl"]
            json_results = self._get_result_json(result_url)

            text_parts = []
            for page_result in json_results:
                result_data = page_result.get("result", {})

                if self.model in self.SUPPORTED_MODELS["layout"]:
                    layout_results = result_data.get("layoutParsingResults", [])
                    for page in layout_results:
                        markdown_obj = page.get("markdown", {})
                        page_text = markdown_obj.get("text", "")
                        if page_text:
                            text_parts.append(page_text)
                else:
                    ocr_results = result_data.get("ocrResults", [])
                    for page in ocr_results:
                        pruned_result = page.get("prunedResult", [])
                        for item in pruned_result:
                            text = item.get("text", "")
                            if text:
                                text_parts.append(text)

            return "\n".join(text_parts)

        except Exception as e:
            print(f"[PaddleX] 图片处理失败: {e}")
            return ""

    def extract_table_from_image(
        self,
        image_path: Union[str, Path],
    ) -> list[dict]:
        """
        从图片提取表格(使用版面解析)

        Args:
            image_path: 图片文件路径

        Returns:
            表格数据列表
        """
        original_model = self.model
        if self.model not in self.SUPPORTED_MODELS["layout"]:
            self.model = "PP-StructureV3"

        result = self.extract_text_from_image(image_path)

        self.model = original_model
        return []

    def is_available(self) -> bool:
        """检查 API 是否可用"""
        try:
            test_file = Path("/tmp/test.txt")
            test_file.write_text("test")
            self._submit_job(test_file)
            return True
        except Exception:
            return False
