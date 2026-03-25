import os
import sys
import tempfile
import shutil
import traceback

from config import logger
from core.env_validator import validate_environment
from core.mineru_client import MinerUConverter
from core.pandoc_runner import compile_format

def process_single_file(input_pdf: str, output_dir: str, format_types: list, pandoc_network: str, formula_mode: str, converter: MinerUConverter):
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
        # 进入解析
        md_path = converter.parse(abs_input, work_dir)

        # 针对每个格式输出
        for fmt in format_types:
            fmt = fmt.strip().lower()
            abs_output = os.path.join(os.path.abspath(output_dir), f"{base_name}.{fmt}")
            logger.info(f"[*] 准备输出格式: {fmt.upper()} -> {abs_output}")
            
            try:
                compile_format(md_path, abs_output, fmt, pandoc_network, formula_mode)
                logger.info(f"[SUCCESS] 文件生成成功: {abs_output}")
            except RuntimeError as e:
                # Pandoc 级别网络阻断应急重试
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

def start_conversion_batch(
    input_pdfs: list, 
    output_dir: str, 
    format_types: list,
    pandoc_network: str = "offline", 
    formula_mode: str = "text",
    cli_api_key: str = ""
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

    # 循环驱动核心
    for idx, pdf in enumerate(input_pdfs, start=1):
        logger.info(f"-> 队列进度 [{idx}/{len(input_pdfs)}]")
        process_single_file(pdf, output_dir, format_types, pandoc_network, formula_mode, converter)
        
    logger.info("=========== 批量转换任务全部结束 ===========")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 命令行模式
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
                cli_api_key=args.api_key
            )
        except Exception as e:
            logger.error(str(e))
            sys.exit(1)
    else:
        # GUI 模式
        from ui.gradio_app import launch_gui
        launch_gui(start_conversion_batch)
