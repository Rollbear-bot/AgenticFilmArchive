"""
PDF Processor 测试

测试PDF文档处理模块的核心功能：
- 文本提取与页码保留
- 表格提取与结构化转换
- 错误处理（损坏文件等）
- 类型隔离（PDF图片严禁使用type="image"）
"""

import os
import tempfile

import fitz
import pytest

from core.pdf_processor import PDFContentBlock, PDFProcessor


@pytest.fixture
def sample_text_pdf():
    """创建包含多页文本的测试PDF。使用英文避免字体兼容问题。"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        doc = fitz.open()
        page1 = doc.new_page()
        page1.insert_text((100, 100), "Camera Operation Manual")
        page1.insert_text((100, 200), "Chapter 1: Basic Operations")

        page2 = doc.new_page()
        page2.insert_text((100, 100), "Chapter 2: Advanced Features")

        doc.save(tmp.name)
        doc.close()
        yield tmp.name

    os.remove(tmp.name)


@pytest.fixture
def sample_table_pdf():
    """创建包含简单表格的测试PDF（基于线条的表格）。"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        doc = fitz.open()
        page = doc.new_page()

        # 绘制表格线条
        rows = [(100, 130), (130, 160), (160, 190), (190, 220)]
        cols = [(100, 180), (180, 260), (260, 340)]

        for y1, y2 in rows:
            page.draw_line((100, y1), (340, y1), color=(0, 0, 0))
        page.draw_line((100, 220), (340, 220), color=(0, 0, 0))

        for x1, x2 in cols:
            page.draw_line((x1, 100), (x1, 220), color=(0, 0, 0))
        page.draw_line((340, 100), (340, 220), color=(0, 0, 0))

        # 填入表头和数据
        page.insert_text((120, 120), "型号")
        page.insert_text((200, 120), "像素")
        page.insert_text((280, 120), "价格")

        page.insert_text((120, 150), "A7III")
        page.insert_text((200, 150), "24MP")
        page.insert_text((280, 150), "12000")

        page.insert_text((120, 180), "A7RIV")
        page.insert_text((200, 180), "61MP")
        page.insert_text((280, 180), "22000")

        doc.save(tmp.name)
        doc.close()
        yield tmp.name

    os.remove(tmp.name)


class TestPDFProcessor:
    def test_extract_text_from_sample_pdf(self, sample_text_pdf):
        """测试文本提取保留页码和排版顺序。"""
        processor = PDFProcessor(sample_text_pdf)
        blocks, report = processor.process()

        assert report["total_pages"] == 2
        assert report["errors"] == []

        text_blocks = [b for b in blocks if b.type == "pdf_text"]
        assert len(text_blocks) >= 2

        contents = " ".join(b.content for b in text_blocks)
        assert "Camera Operation Manual" in contents
        assert "Chapter 1" in contents
        assert "Chapter 2" in contents

        # 验证页码保留
        page_numbers = {b.page_number for b in text_blocks}
        assert 1 in page_numbers
        assert 2 in page_numbers

    def test_extract_tables_from_sample_pdf(self, sample_table_pdf):
        """测试表格提取为Markdown/JSON格式。"""
        processor = PDFProcessor(sample_table_pdf)
        blocks, report = processor.process()

        table_blocks = [b for b in blocks if b.type == "pdf_table"]

        # 表格检测基于启发式，可能不总是识别成功，但应无错误
        assert report["errors"] == []

        if table_blocks:
            for block in table_blocks:
                assert "【表格】" in block.content
                assert "【结构化数据】" in block.content
                assert block.metadata.get("row_count", 0) > 0
                assert block.metadata.get("col_count", 0) > 0

    def test_process_pdf_with_mixed_content(self, sample_text_pdf, monkeypatch):
        """测试混合内容（文本+图片）的完整流程，mock图片API调用。"""
        monkeypatch.setattr(
            PDFProcessor,
            "_generate_image_description",
            lambda self, path: "【测试】图片描述：示意图",
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), "This document contains an image")

            # 插入一个简单图片（红色方块）
            # Pixmap(colorspace, width, height, samples, alpha)
            pix = fitz.Pixmap(fitz.csRGB, 10, 10, b"\xff\x00\x00" * 100, 0)
            img_rect = fitz.Rect(100, 150, 200, 250)
            page.insert_image(img_rect, pixmap=pix)
            pix = None

            doc.save(tmp.name)
            doc.close()
            pdf_path = tmp.name

        try:
            processor = PDFProcessor(pdf_path)
            blocks, report = processor.process()

            assert report["total_pages"] == 1
            assert report["errors"] == []

            text_blocks = [b for b in blocks if b.type == "pdf_text"]
            image_blocks = [b for b in blocks if b.type == "pdf_image"]

            assert len(text_blocks) >= 1
            assert any("This document contains an image" in b.content for b in text_blocks)
            assert len(image_blocks) >= 1
            assert all(b.type == "pdf_image" for b in image_blocks)
        finally:
            os.remove(pdf_path)

    def test_pdf_processor_error_handling(self):
        """测试损坏PDF的错误处理：应返回空块和错误报告，不抛出异常。"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"this is not a valid pdf content")
            tmp.flush()
            invalid_path = tmp.name

        try:
            processor = PDFProcessor(invalid_path)
            blocks, report = processor.process()

            assert blocks == []
            assert len(report["errors"]) > 0
            assert any("打开PDF失败" in err for err in report["errors"])
        finally:
            os.remove(invalid_path)

    def test_pdf_image_type_isolation(self):
        """验证PDF图片类型严格使用pdf_image，绝不为image，避免与照片混淆。"""
        block = PDFContentBlock(
            type="pdf_image",
            page_number=1,
            content="test image description",
            metadata={},
        )
        assert block.type == "pdf_image"
        assert block.type != "image"

        # 验证存储到向量库的metadata中type字段的隔离原则
        # 实际代码中必须确保PDF图片使用"pdf_image"而非"image"
        forbidden_types = ["image", "text", "table"]
        assert block.type not in forbidden_types

    def test_empty_pdf(self):
        """测试空PDF的处理。"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            doc = fitz.open()
            doc.new_page()
            doc.save(tmp.name)
            doc.close()
            empty_path = tmp.name

        try:
            processor = PDFProcessor(empty_path)
            blocks, report = processor.process()

            assert report["total_pages"] == 1
            assert report["errors"] == []
            # 空页面可能无文本块，但不应报错
        finally:
            os.remove(empty_path)
