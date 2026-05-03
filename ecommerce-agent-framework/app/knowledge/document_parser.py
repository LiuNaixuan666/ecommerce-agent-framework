# document_parser.py
import os
import logging
import pandas as pd
from typing import List, Dict
from pypdf import PdfReader
from docx import Document

logger = logging.getLogger(__name__)

class DocumentParser:
    """
    通用文档解析器：支持 PDF, DOCX, XLSX, CSV, TXT
    对应论文中的 Knowledge Ingestion 模块
    """
    
    @staticmethod
    def parse_pdf(file_path: str) -> str:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text

    @staticmethod
    def parse_docx(file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    @staticmethod
    def parse_excel_csv(file_path: str) -> str:
        # 自动识别是 CSV 还是 Excel
        # 使用字符串类型读取并填充缺失值，避免 NaN/非字符串导致拼接问题
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str).fillna('')
        else:
            df = pd.read_excel(file_path, dtype=str).fillna('')

        # 将表格数据转化为语义化的文本，方便 LLM 理解
        # 例如: "Column1: Value1, Column2: Value2"
        lines = []
        for _, row in df.iterrows():
            parts = []
            for col, val in row.items():
                parts.append(f"{col}: {'' if val is None else str(val)}")
            lines.append(", ".join(parts))

        return "\n".join(lines)

    def load_merchant_data(self, merchant_dir: str) -> List[Dict[str, str]]:
        """
        遍历商家目录，读取所有支持的文件
        返回格式: [{"source": "filename", "content": "text_content"}]
        """
        documents = []
        if not os.path.exists(merchant_dir):
            return documents

        # 使用 os.walk 递归遍历所有子文件夹
        for root, dirs, files in os.walk(merchant_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                ext = filename.split('.')[-1].lower()
                content = ""
                if not os.path.isfile(file_path):
                    continue
                ext = filename.split('.')[-1].lower()
                content = ""

                try:
                    if ext == 'pdf':
                        content = self.parse_pdf(file_path)
                    elif ext == 'docx':
                        content = self.parse_docx(file_path)
                    elif ext in ['xlsx', 'xls', 'csv']:
                        content = self.parse_excel_csv(file_path)
                    elif ext in ['txt', 'md']:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    
                    if content:
                        documents.append({"source": filename, "content": content})
                except Exception as e:
                    logger.exception(f"Error parsing {filename}")
                
        return documents