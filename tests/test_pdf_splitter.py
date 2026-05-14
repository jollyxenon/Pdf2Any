"""Tests for core/pdf_splitter.py — split, merge, cleanup logic"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from pypdf import PdfWriter  # type: ignore[import-unresolved]

from core.pdf_splitter import (
    get_page_count,
    split_pdf,
    merge_markdown_results,
    cleanup_chunks,
)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a minimal multi-page PDF for testing."""
    writer = PdfWriter()
    for _ in range(10):
        writer.add_blank_page(width=612, height=792)
    pdf_path = tmp_path / "sample.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def large_pdf(tmp_path: Path) -> Path:
    """Create a 320-page PDF for chunking tests."""
    writer = PdfWriter()
    for _ in range(320):
        writer.add_blank_page(width=612, height=792)
    pdf_path = tmp_path / "large.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


class TestGetPageCount:
    def test_normal_pdf(self, sample_pdf: Path):
        assert get_page_count(str(sample_pdf)) == 10

    def test_large_pdf(self, large_pdf: Path):
        assert get_page_count(str(large_pdf)) == 320

    def test_corrupted_pdf(self, tmp_path: Path):
        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_text("this is not a pdf")
        with pytest.raises(RuntimeError):
            get_page_count(str(bad_pdf))


class TestSplitPdf:
    def test_split_exceeds_threshold(self, large_pdf: Path, tmp_path: Path):
        output_dir = tmp_path / "chunks"
        chunks = split_pdf(str(large_pdf), str(output_dir), max_pages=150)

        assert len(chunks) == 3
        assert all(p.exists() for p in chunks)

        from pypdf import PdfReader  # type: ignore[import-unresolved]
        page_counts = [len(PdfReader(str(c)).pages) for c in chunks]
        assert page_counts == [150, 150, 20]

    def test_split_equal_to_threshold(self, tmp_path: Path):
        writer = PdfWriter()
        for _ in range(150):
            writer.add_blank_page(width=612, height=792)
        pdf_path = tmp_path / "exact.pdf"
        with open(pdf_path, "wb") as f:
            writer.write(f)

        output_dir = tmp_path / "chunks"
        chunks = split_pdf(str(pdf_path), str(output_dir), max_pages=150)
        assert len(chunks) == 1

    def test_split_below_threshold(self, sample_pdf: Path, tmp_path: Path):
        output_dir = tmp_path / "chunks"
        chunks = split_pdf(str(sample_pdf), str(output_dir), max_pages=150)
        assert len(chunks) == 1


class TestMergeMarkdownResults:
    def test_merge_multiple_chunks(self, tmp_path: Path):
        chunk_results = []
        for i in range(3):
            work_dir = tmp_path / f"work_{i}"
            work_dir.mkdir()
            images_dir = work_dir / "images"
            images_dir.mkdir()

            (images_dir / "0.jpg").write_text(f"image_data_{i}")
            (images_dir / "1.jpg").write_text(f"image_data_{i}_1")

            md_path = work_dir / "output.md"
            md_path.write_text(f"# Chunk {i}\n\n![fig](images/0.jpg)\n![fig2](images/1.jpg)\n")

            chunk_results.append((md_path, work_dir))

        output_dir = tmp_path / "merged"
        merged_md = merge_markdown_results(chunk_results, str(output_dir))

        assert merged_md.exists()
        content = merged_md.read_text(encoding="utf-8")

        assert "# Chunk 0" in content
        assert "# Chunk 1" in content
        assert "# Chunk 2" in content

        merged_images = output_dir / "images"
        assert merged_images.exists()
        image_files = sorted(f.name for f in merged_images.iterdir())
        assert "chunk0_0.jpg" in image_files
        assert "chunk1_0.jpg" in image_files
        assert "chunk2_0.jpg" in image_files

    def test_image_path_dedup(self, tmp_path: Path):
        chunk_results = []
        for i in range(2):
            work_dir = tmp_path / f"work_{i}"
            work_dir.mkdir()
            images_dir = work_dir / "images"
            images_dir.mkdir()
            (images_dir / "fig.png").write_text(f"data_{i}")

            md_path = work_dir / "output.md"
            md_path.write_text(f"![alt](images/fig.png)\n")
            chunk_results.append((md_path, work_dir))

        output_dir = tmp_path / "merged"
        merged_md = merge_markdown_results(chunk_results, str(output_dir))
        content = merged_md.read_text(encoding="utf-8")

        assert "chunk0_fig.png" in content
        assert "chunk1_fig.png" in content

        merged_images = output_dir / "images"
        assert (merged_images / "chunk0_fig.png").exists()
        assert (merged_images / "chunk1_fig.png").exists()


class TestCleanupChunks:
    def test_cleanup_removes_files_and_dirs(self, tmp_path: Path):
        chunk_pdf = tmp_path / "chunk0.pdf"
        chunk_pdf.write_text("fake pdf")
        work_dir = tmp_path / "work_0"
        work_dir.mkdir()
        (work_dir / "output.md").write_text("content")

        cleanup_chunks([chunk_pdf], [work_dir])

        assert not chunk_pdf.exists()
        assert not work_dir.exists()

    def test_cleanup_handles_missing_files(self, tmp_path: Path):
        nonexistent_pdf = tmp_path / "gone.pdf"
        nonexistent_dir = tmp_path / "gone_dir"
        cleanup_chunks([nonexistent_pdf], [nonexistent_dir])


class TestProcessSingleFileChunking:
    @patch("main.MinerUConverter")
    def test_chunked_flow_called_for_large_pdf(self, mock_converter_cls, large_pdf: Path, tmp_path: Path):
        from main import process_single_file

        mock_converter = MagicMock()
        mock_converter.parse.return_value = str(tmp_path / "fake.md")
        (tmp_path / "fake.md").write_text("# Parsed content")

        with patch("main.get_page_count", return_value=320):
            with patch("main._process_chunked", return_value=str(tmp_path / "fake.md")) as mock_chunked:
                process_single_file(
                    str(large_pdf), str(tmp_path / "output"), ["md"], "offline", "text",
                    mock_converter, max_pages=150
                )
                mock_chunked.assert_called_once()

    @patch("main.MinerUConverter")
    def test_direct_parse_for_small_pdf(self, mock_converter_cls, sample_pdf: Path, tmp_path: Path):
        from main import process_single_file

        mock_converter = MagicMock()
        fake_md = tmp_path / "work" / "output.md"
        fake_md.parent.mkdir(parents=True, exist_ok=True)
        fake_md.write_text("# Small PDF")
        mock_converter.parse.return_value = str(fake_md)

        with patch("main.get_page_count", return_value=10):
            with patch("main._process_chunked") as mock_chunked:
                process_single_file(
                    str(sample_pdf), str(tmp_path / "output"), ["md"], "offline", "text",
                    mock_converter, max_pages=150
                )
                mock_chunked.assert_not_called()
                mock_converter.parse.assert_called_once()
