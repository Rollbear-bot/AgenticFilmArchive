"""
PDF Processor - PDF文档处理模块

处理包含文本、图片、表格混合编排的多页PDF文档。
PDF中的图片与知识库中的照片性质完全不同，
因此内部类型统一使用 "pdf_image"，严禁使用 "image"，
避免被现有照片处理逻辑（如标签生成、缩略图展示）误识别。
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from typing import Literal

import fitz  # pymupdf
import pandas as pd

from configures import CHAT_MODEL
from core.services import get_image_client, image_to_base64


@dataclass
class PDFContentBlock:
    """PDF内容块，统一表示提取的各类内容。

    重要原则：PDF中的图片与知识库中的照片（type="image"）性质完全不同，
    因此内部枚举和入库metadata均使用 "pdf_image"，严禁使用 "image"，
    避免被现有照片处理逻辑（如标签生成、缩略图展示）误识别。
    """

    type: Literal["pdf_text", "pdf_image", "pdf_table"]
    page_number: int
    content: str
    metadata: dict = field(default_factory=dict)


class PDFProcessor:
    """PDF处理器，提取文本、图片、表格等结构化内容。"""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.file_name = os.path.basename(pdf_path)

    def process(self) -> tuple[list[PDFContentBlock], dict]:
        """处理PDF，返回内容块列表和处理状态报告。

        Returns:
            (blocks, report): blocks为PDFContentBlock列表，report包含处理统计和错误信息
        """
        blocks: list[PDFContentBlock] = []
        report = {
            "total_pages": 0,
            "text_blocks": 0,
            "image_blocks": 0,
            "table_blocks": 0,
            "errors": [],
        }

        try:
            doc = fitz.open(self.pdf_path)
        except Exception as e:
            report["errors"].append(f"打开PDF失败: {e}")
            return blocks, report

        report["total_pages"] = len(doc)

        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            page_number = page_idx + 1

            try:
                # 提取文本
                text_blocks = self._extract_text_blocks(page, page_number)
                blocks.extend(text_blocks)
                report["text_blocks"] += len(text_blocks)

                # 提取图片
                image_blocks = self._extract_images(page, page_number)
                blocks.extend(image_blocks)
                report["image_blocks"] += len(image_blocks)

                # 提取表格
                table_blocks = self._extract_tables(page, page_number)
                blocks.extend(table_blocks)
                report["table_blocks"] += len(table_blocks)

            except Exception as e:
                report["errors"].append(f"第{page_number}页处理失败: {e}")

        doc.close()
        return blocks, report

    def _extract_text_blocks(self, page: fitz.Page, page_number: int) -> list[PDFContentBlock]:
        """按段落/块提取文本，保留原始排版顺序和页码。"""
        blocks: list[PDFContentBlock] = []
        text_blocks = page.get_text("blocks")

        for b in text_blocks:
            # b 格式: (x0, y0, x1, y1, text, block_no, block_type)
            text = b[4].strip()
            if not text:
                continue

            blocks.append(
                PDFContentBlock(
                    type="pdf_text",
                    page_number=page_number,
                    content=text,
                    metadata={
                        "bbox": b[:4],
                        "block_no": b[5],
                    },
                )
            )

        # 如果get_text("blocks")未返回内容，尝试直接提取全文
        if not blocks:
            full_text = page.get_text().strip()
            if full_text:
                blocks.append(
                    PDFContentBlock(
                        type="pdf_text",
                        page_number=page_number,
                        content=full_text,
                        metadata={},
                    )
                )

        return blocks

    def _extract_images(self, page: fitz.Page, page_number: int) -> list[PDFContentBlock]:
        """提取页面中的图片，使用多模态模型生成描述文本。"""
        blocks: list[PDFContentBlock] = []
        images = page.get_images(full=True)

        for img in images:
            xref = img[0]
            tmp_path = None
            try:
                pix = fitz.Pixmap(page.parent, xref)
                if pix.n > 4:  # CMYK: 转换为RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                width, height = pix.width, pix.height

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                    pix.save(tmp_path)
                pix = None

                description = self._generate_image_description(tmp_path)

                blocks.append(
                    PDFContentBlock(
                        type="pdf_image",
                        page_number=page_number,
                        content=description,
                        metadata={
                            "xref": xref,
                            "width": width,
                            "height": height,
                        },
                    )
                )

            except Exception:
                # 跳过损坏或无法处理的图片
                continue
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)

        return blocks

    def _generate_image_description(self, image_path: str) -> str:
        """使用Ark多模态模型生成图片描述。

        复用现有services.get_image_client()和image_to_base64()，
        不引入新的外部依赖。
        """
        try:
            image_url = image_to_base64(image_path)
            client = get_image_client()

            completion = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}},
                            {
                                "type": "text",
                                "text": "请描述这张图片的内容。如果图片包含文字，请提取并说明。请用简洁的中文回答。",
                            },
                        ],
                    }
                ],
                reasoning_effort="medium",
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"图片描述生成失败: {str(e)}"

    def _extract_tables(self, page: fitz.Page, page_number: int) -> list[PDFContentBlock]:
        """提取页面中的表格，转为Markdown表格格式并附带JSON结构化摘要。"""
        blocks: list[PDFContentBlock] = []

        try:
            table_finder = page.find_tables()
            tables = table_finder.tables
        except Exception:
            return blocks

        for tab in tables:
            try:
                df = tab.to_pandas()
                if df.empty:
                    continue

                # 生成Markdown表格
                markdown_table = df.to_markdown(index=False)

                # 生成JSON摘要
                json_summary = {
                    "columns": df.columns.tolist(),
                    "row_count": len(df),
                    "col_count": len(df.columns),
                    "sample_data": df.head(3).to_dict(orient="records"),
                }

                content = (
                    f"【表格】\n\n{markdown_table}\n\n"
                    f"【结构化数据】\n"
                    f"{json.dumps(json_summary, ensure_ascii=False, indent=2)}"
                )

                blocks.append(
                    PDFContentBlock(
                        type="pdf_table",
                        page_number=page_number,
                        content=content,
                        metadata={
                            "row_count": len(df),
                            "col_count": len(df.columns),
                        },
                    )
                )

            except Exception:
                continue

        return blocks
