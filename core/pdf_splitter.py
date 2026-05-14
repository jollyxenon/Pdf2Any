"""PDF 分片模块：检测页数、拆分子文件、合并结果、清理临时文件"""

import os
import re
import shutil
from pathlib import Path

from pypdf import PdfReader, PdfWriter  # type: ignore[import-unresolved]
from config import logger


def get_page_count(pdf_path: str) -> int:
    """获取 PDF 文件的总页数

    Args:
        pdf_path: PDF 文件路径

    Returns:
        页数（int）

    Raises:
        RuntimeError: 文件损坏或无法读取时抛出
    """
    try:
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as e:
        raise RuntimeError(f"无法读取 PDF 页数: {pdf_path}, 错误: {e}")


def split_pdf(pdf_path: str, output_dir: str, max_pages: int = 150) -> list[Path]:
    """按固定页数将 PDF 拆分为多个临时子文件

    Args:
        pdf_path: 源 PDF 文件路径
        output_dir: 子文件输出目录
        max_pages: 每个分片的最大页数（默认 150）

    Returns:
        生成的子 PDF 文件路径列表（按顺序）

    Raises:
        RuntimeError: 拆分失败时抛出
    """
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        base_name = Path(pdf_path).stem

        os.makedirs(output_dir, exist_ok=True)

        chunk_paths: list[Path] = []
        chunk_index = 0

        for start in range(0, total_pages, max_pages):
            end = min(start + max_pages, total_pages)
            writer = PdfWriter()

            for page_num in range(start, end):
                writer.add_page(reader.pages[page_num])

            chunk_filename = f"{base_name}_chunk{chunk_index}.pdf"
            chunk_path = Path(output_dir) / chunk_filename
            with open(chunk_path, "wb") as f:
                writer.write(f)

            chunk_paths.append(chunk_path)
            logger.info(f"[分片] 生成子文件: {chunk_filename} (页 {start+1}-{end})")
            chunk_index += 1

        return chunk_paths

    except Exception as e:
        raise RuntimeError(f"PDF 拆分失败: {pdf_path}, 错误: {e}")


def merge_markdown_results(
    chunk_results: list[tuple[Path, Path]], output_dir: str
) -> Path:
    """合并多个分片的 Markdown 结果和图片目录

    将各分片的 .md 内容按顺序拼接，并将图片文件合并到统一的 images/ 目录中，
    使用 chunk{N}_ 前缀避免文件名冲突。

    Args:
        chunk_results: 每个元素为 (md_file_path, work_dir_path) 的元组列表，
                       work_dir_path 中可能包含 images/ 子目录
        output_dir: 合并结果的输出目录

    Returns:
        合并后的 Markdown 文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    merged_images_dir = Path(output_dir) / "images"
    os.makedirs(merged_images_dir, exist_ok=True)

    merged_md_lines: list[str] = []

    for chunk_idx, (md_path, work_dir) in enumerate(chunk_results):
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        images_dir = _find_images_dir(work_dir)

        if images_dir and images_dir.exists():
            for img_file in images_dir.iterdir():
                if img_file.is_file():
                    new_name = f"chunk{chunk_idx}_{img_file.name}"
                    shutil.copy2(img_file, merged_images_dir / new_name)

                    old_ref = img_file.name
                    new_ref = f"chunk{chunk_idx}_{old_ref}"
                    md_content = md_content.replace(old_ref, new_ref)

        merged_md_lines.append(md_content)

    merged_content = "\n\n".join(merged_md_lines)
    merged_content = _normalize_image_paths(merged_content)

    merged_md_path = Path(output_dir) / "merged_output.md"
    with open(merged_md_path, "w", encoding="utf-8") as f:
        f.write(merged_content)

    logger.info(f"[合并] Markdown 合并完成: {merged_md_path}")
    return merged_md_path


def cleanup_chunks(
    chunk_paths: list[Path], chunk_work_dirs: list[Path]
) -> None:
    """清理分片过程中产生的所有临时文件

    Args:
        chunk_paths: 临时子 PDF 文件路径列表
        chunk_work_dirs: 各分片的工作目录列表
    """
    for p in chunk_paths:
        try:
            if p.exists():
                os.remove(p)
        except OSError as e:
            logger.warning(f"[清理] 删除临时 PDF 失败: {p}, {e}")

    for d in chunk_work_dirs:
        try:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
        except OSError as e:
            logger.warning(f"[清理] 删除工作目录失败: {d}, {e}")

    logger.info("[清理] 分片临时文件清理完成")


def _find_images_dir(work_dir: Path) -> Path | None:
    """在工作目录中查找 images 子目录（MinerU 输出结构中的图片目录）"""
    direct = work_dir / "images"
    if direct.exists() and direct.is_dir():
        return direct

    for root, dirs, _ in os.walk(work_dir):
        if "images" in dirs:
            return Path(root) / "images"

    return None


def _normalize_image_paths(md_content: str) -> str:
    """将 Markdown 中的图片路径统一为 images/ 相对路径格式

    处理 MinerU 可能产生的各种路径格式，统一为 images/filename 形式。
    """
    def replace_path(match: "re.Match[str]") -> str:
        alt = match.group(1)
        path = match.group(2)
        filename = Path(path).name
        return f"![{alt}](images/{filename})"

    pattern = r"!\[([^\]]*)\]\(([^)]*chunk\d+_[^)]+)\)"
    return re.sub(pattern, replace_path, md_content)
