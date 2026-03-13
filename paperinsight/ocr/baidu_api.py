"""
百度 OCR API 模块
功能: 调用百度 OCR API 进行文本识别
"""

import base64
import json
import time
from pathlib import Path
from typing import Optional, Tuple, Union

import requests

from paperinsight.ocr.base import BaseOCR


class BaiduOCRAPI(BaseOCR):
    """百度 OCR API 引擎"""
    
    # API 端点
    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    DOC_ANALYSIS_URL = "https://aip.baidubce.com/rest/2.0/solution/v1/doc_analysis/request"
    GENERAL_BASIC_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
    ACCURATE_BASIC_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
    TABLE_URL = "https://aip.baidubce.com/rest/2.0/solution/v1/form_ocr/request"
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        language: str = "CHN_ENG",
        timeout: int = 60,
    ):
        """
        初始化百度 OCR API 引擎
        
        Args:
            api_key: 百度云 API Key
            secret_key: 百度云 Secret Key
            language: 语言类型 ('CHN_ENG', 'ENG', 'CHN' 等)
            timeout: 请求超时时间(秒)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.language = language
        self.timeout = timeout
        self._access_token = None
        self._token_expire_time = 0
    
    def _get_access_token(self) -> str:
        """
        获取 Access Token
        
        Returns:
            Access Token
        """
        # 检查缓存的 token 是否有效
        if self._access_token and time.time() < self._token_expire_time:
            return self._access_token
        
        # 请求新的 token
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }
        
        try:
            response = requests.post(self.TOKEN_URL, params=params, timeout=self.timeout)
            result = response.json()
            
            if "error" in result:
                raise ValueError(f"获取 Access Token 失败: {result.get('error_description', result['error'])}")
            
            self._access_token = result["access_token"]
            # Token 有效期 30 天,提前 1 小时刷新
            self._token_expire_time = time.time() + result.get("expires_in", 2592000) - 3600
            
            return self._access_token
        
        except Exception as e:
            raise RuntimeError(f"获取百度 OCR Access Token 失败: {e}") from e
    
    def _encode_file(self, file_path: Union[str, Path]) -> str:
        """
        将文件编码为 Base64
        
        Args:
            file_path: 文件路径
        
        Returns:
            Base64 编码字符串
        """
        path = Path(file_path)
        with path.open("rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _make_request(
        self,
        url: str,
        data: dict,
        retry_count: int = 3,
    ) -> dict:
        """
        发送 API 请求
        
        Args:
            url: API 端点
            data: 请求数据
            retry_count: 重试次数
        
        Returns:
            API 响应
        """
        access_token = self._get_access_token()
        url_with_token = f"{url}?access_token={access_token}"
        
        for attempt in range(retry_count):
            try:
                response = requests.post(
                    url_with_token,
                    data=data,
                    timeout=self.timeout,
                )
                result = response.json()
                
                # 检查错误
                if "error_code" in result:
                    error_code = result["error_code"]
                    
                    # 如果是 token 过期,刷新后重试
                    if error_code in (100, 110, 111):
                        self._access_token = None
                        access_token = self._get_access_token()
                        url_with_token = f"{url}?access_token={access_token}"
                        continue
                    
                    raise RuntimeError(f"百度 OCR API 错误: {result.get('error_msg', error_code)}")
                
                return result
            
            except requests.exceptions.Timeout:
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError("百度 OCR API 请求超时")
            
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"百度 OCR API 请求失败: {e}")
        
        raise RuntimeError("百度 OCR API 请求失败")
    
    def extract_text_from_pdf(
        self,
        pdf_path: Union[str, Path],
        max_pages: Optional[int] = None,
    ) -> Tuple[str, str, dict]:
        """
        从 PDF 提取文本(使用文档解析 API)
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大读取页数
        
        Returns:
            (full_text, front_text, metadata)
        """
        pdf_path = Path(pdf_path)
        
        try:
            # 编码文件
            image_base64 = self._encode_file(pdf_path)
            
            # 调用文档解析 API
            data = {
                "image": image_base64,
                "language_type": self.language,
                "result_type": "bigText",  # 返回大段文本
            }
            
            result = self._make_request(self.DOC_ANALYSIS_URL, data)
            
            # 解析结果
            if "results" not in result:
                return "", "", {}
            
            full_text_parts = []
            front_text = ""
            
            for idx, page_result in enumerate(result.get("results", [])):
                if max_pages is not None and idx >= max_pages:
                    break
                
                # 提取页面文本
                words = page_result.get("words", [])
                page_text = "\n".join(words) if words else ""
                
                if page_text:
                    full_text_parts.append(page_text)
                    if not front_text:
                        front_text = page_text
            
            full_text = "\n\n".join(full_text_parts)
            return full_text, front_text, {}
        
        except Exception as e:
            print(f"[百度 OCR] PDF 处理失败: {e}")
            return "", "", {}
    
    def extract_text_from_image(
        self,
        image_path: Union[str, Path],
        use_accurate: bool = True,
    ) -> str:
        """
        从图片提取文本
        
        Args:
            image_path: 图片文件路径
            use_accurate: 是否使用高精度版本
        
        Returns:
            提取的文本
        """
        image_path = Path(image_path)
        
        try:
            # 编码文件
            image_base64 = self._encode_file(image_path)
            
            # 选择 API
            url = self.ACCURATE_BASIC_URL if use_accurate else self.GENERAL_BASIC_URL
            
            data = {
                "image": image_base64,
                "language_type": self.language,
            }
            
            result = self._make_request(url, data)
            
            # 提取文本
            words_result = result.get("words_result", [])
            text_parts = [item.get("words", "") for item in words_result]
            
            return "\n".join(text_parts)
        
        except Exception as e:
            print(f"[百度 OCR] 图片处理失败: {e}")
            return ""
    
    def extract_table_from_image(
        self,
        image_path: Union[str, Path],
    ) -> list[dict]:
        """
        从图片提取表格
        
        Args:
            image_path: 图片文件路径
        
        Returns:
            表格数据列表
        """
        image_path = Path(image_path)
        
        try:
            # 编码文件
            image_base64 = self._encode_file(image_path)
            
            data = {
                "image": image_base64,
            }
            
            result = self._make_request(self.TABLE_URL, data)
            
            return result.get("tables_result", [])
        
        except Exception as e:
            print(f"[百度 OCR] 表格提取失败: {e}")
            return []
    
    def is_available(self) -> bool:
        """检查 API 是否可用"""
        try:
            self._get_access_token()
            return True
        except Exception:
            return False
