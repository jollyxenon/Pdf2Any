import os
import sys
import tempfile
import shutil
import traceback
from pathlib import Path

from config import logger
from core.env_validator import validate_environment
from core.mineru_client import MinerUConverter
from core.pandoc_runner import compile_format
from core.pdf_splitter import get_page_count, split_pdf, merge_markdown_results, cleanup_chunks


def process_single_file(
    input_pdf: str,
    output_dir: str,
    format_types: list,
    pandoc_network: str,
    formula_mode: str,
    converter: MinerUConverter,
    max_pages: int = 150,
):
    logger.info(f"\n=============================================\n--- 开始处理队列文件: {input_pdf} ---")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_pdf) or not input_pdf.lower().endswith(".pdf"):
        logger.error(f"跳过不合法的 PDF 文件: {input_pdf}")
        return

    abs_input = os.path.abspath(input_pdf)
    work_dir = tempfile.mkdtemp(prefix="pdf_project_")
    base_name = os.path.splitext(os.path.basename(abs_input))[0]

    try:
        page_count = get_page_count(abs_input)
        logger.info(f"[*] PDF 页数: {page_count}, 分片阈值: {max_pages}")

        if page_count > max_pages:
            md_path = _process_chunked(abs_input, work_dir, max_pages, converter)
        else:
            md_path = converter.parse(abs_input, work_dir)

        for fmt in format_types:
            fmt = fmt.strip().lower()
            abs_output = os.path.join(os.path.abspath(output_dir), f"{base_name}.{fmt}")
            logger.info(f"[*] 准备输出格式: {fmt.upper()} -> {abs_output}")

            try:
                compile_format(md_path, abs_output, fmt, pandoc_network, formula_mode)
                logger.info(f"[SUCCESS] 文件生成成功: {abs_output}")
            except RuntimeError as e:
                if "Network Timeout" in str(e):
                    if formula_mode == "image" or pandoc_network == "online":
                        logger.warning("[WARNING] Pandoc 网络连接超时或被阻断 (WebTex 引起)！")
                        logger.warning("[*] 自动降级使用本地原生的 --mathml 文本方式重新渲染...")
                        compile_format(md_path, abs_output, fmt, "offline", "text")
                        logger.info(f"[SUCCESS] 文件(降级渲染)生成成功: {abs_output}")
                    else:
                        raise RuntimeError("Pandoc 离线状态依然发生未知连接超时。")
                else:
                    raise
        logger.info(f"--- 队列文件 {base_name} 处理彻底完成 ---")

    except Exception as e:
        err_detail = traceback.format_exc()
        logger.error(f"转换单个文件时发生致命错误:\n{e}\n{err_detail}")
        logger.error(f"[*] 已跳过文件 {base_name}，将继续队列...")
    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


def _process_chunked(abs_input: str, work_dir: str, max_pages: int, converter: MinerUConverter) -> str:
    chunk_dir = os.path.join(work_dir, "chunks")
    merge_dir = os.path.join(work_dir, "merged")

    logger.info(f"[分片] 开始拆分大型 PDF（阈值 {max_pages} 页）...")
    chunk_paths = split_pdf(abs_input, chunk_dir, max_pages)
    logger.info(f"[分片] 共生成 {len(chunk_paths)} 个子文件")

    chunk_results: list[tuple[Path, Path]] = []
    chunk_work_dirs: list[Path] = []

    try:
        for idx, chunk_pdf in enumerate(chunk_paths):
            logger.info(f"[分片] 正在转换第 {idx + 1}/{len(chunk_paths)} 个分片: {chunk_pdf.name}")
            chunk_work = tempfile.mkdtemp(prefix=f"chunk{idx}_", dir=work_dir)
            chunk_work_path = Path(chunk_work)
            chunk_work_dirs.append(chunk_work_path)

            try:
                md_path = converter.parse(str(chunk_pdf), chunk_work)
                chunk_results.append((Path(md_path), chunk_work_path))
            except Exception as e:
                logger.error(f"[分片] 第 {idx + 1} 个分片转换失败: {e}")
                raise RuntimeError(f"分片 {idx + 1}/{len(chunk_paths)} 转换失败: {e}")

        logger.info("[分片] 所有分片转换完成，开始合并结果...")
        merged_md = merge_markdown_results(chunk_results, merge_dir)
        return str(merged_md)

    finally:
        cleanup_chunks(chunk_paths, chunk_work_dirs)


def start_conversion_batch(
    input_pdfs: list,
    output_dir: str,
    format_types: list,
    pandoc_network: str = "offline",
    formula_mode: str = "text",
    cli_api_key: str = "",
    max_pages: int = 150,
):
    logger.info("=========== 开始批量转换任务 ===========")
    logger.info(f"待处理队列文件数: {len(input_pdfs)}")
    logger.info(f"选定输出文件夹: {output_dir}")
    logger.info(f"要求格式: {format_types}")

    validate_environment()

    api_keys = []
    env_key = os.getenv("MINERU_API_TOKEN")
    if env_key:
        api_keys.append(env_key)
    if cli_api_key:
        api_keys.append(cli_api_key)

    converter = MinerUConverter(api_keys=api_keys)

    for idx, pdf in enumerate(input_pdfs, start=1):
        logger.info(f"-> 队列进度 [{idx}/{len(input_pdfs)}]")
        process_single_file(pdf, output_dir, format_types, pandoc_network, formula_mode, converter, max_pages)

    logger.info("=========== 批量转换任务全部结束 ===========")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        from ui.cli_parser import get_parser
        parser = get_parser()
        args = parser.parse_args()

        try:
            start_conversion_batch(
                input_pdfs=args.input,
                output_dir=args.output,
                format_types=args.format,
                pandoc_network=args.network,
                formula_mode=args.formula,
                cli_api_key=args.api_key,
                max_pages=args.max_pages,
            )
        except Exception as e:
            logger.error(str(e))
            sys.exit(1)
    else:
        from ui.gradio_app import launch_gui
        launch_gui(start_conversion_batch)
