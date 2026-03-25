import os
import shutil
import subprocess
from config import logger

def compile_format(md_path: str, output_path: str, format_type: str, pandoc_network: str, formula_mode: str):
    if format_type.lower() == "md":
        logger.info("[*] 用户选择了 Markdown 输出，正在复制解析结果...")
        if os.path.exists(output_path) and os.path.isdir(output_path):
            output_path = os.path.join(output_path, os.path.basename(md_path))
        shutil.copy2(md_path, output_path)
        md_dir = os.path.dirname(md_path)
        images_dir = os.path.join(md_dir, "images")
        if os.path.exists(images_dir):
            out_img_dir = os.path.join(os.path.dirname(output_path), "images")
            if os.path.exists(out_img_dir):
                shutil.rmtree(out_img_dir)
            shutil.copytree(images_dir, out_img_dir)
        return

    logger.info(f"[*] 启动 Pandoc 进行 {format_type.upper()} 编译... (网络模式={pandoc_network}, 公式模式={formula_mode})")
    cmd = ["pandoc", md_path, "-o", output_path]
    
    if format_type.lower() == "epub":
        cmd.append("--epub-chapter-level=2")
    
    if format_type.lower() == "pdf":
        # 解析①②③等特殊序号，需要通过 header 告知 xeCJK 将该 Unicode 区块 (U+2460-U+24FF) 视为 CJK 字符
        cmd.extend([
            "--pdf-engine=xelatex", 
            "-V", "CJKmainfont=Microsoft YaHei",
            "-V", r"header-includes=\usepackage{xeCJK}",
            "-V", r'header-includes=\xeCJKDeclareCharClass{CJK}{"2460->"24FF}'
        ])

    if formula_mode == "image":
        if pandoc_network == "offline":
            logger.warning("[WARNING] 请求离线模式但要求图片形式公式！将强行传递 --webtex，此时依旧会有网络请求！")
        cmd.append("--webtex=https://latex.codecogs.com/svg.image?")
    else:  # text
        if format_type.lower() in ["epub", "html"]:
            cmd.append("--mathml")
            
    try:
        process = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        if process.stdout:
            logger.info(process.stdout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Network Timeout")
    except subprocess.CalledProcessError as e:
        error_info = e.stderr.lower() if e.stderr else ""
        if "network" in error_info or "timeout" in error_info or "socket" in error_info or "connection" in error_info:
            raise RuntimeError("Network Timeout")
        elif "pdflatex not found" in error_info or "xelatex not found" in error_info:
            raise RuntimeError(f"导出 {format_type.upper()} 失败：未能在系统中找到 LaTeX 引擎 (pdflatex/xelatex)。请安装 TeXLive 或 MiKTeX 等后重试。")
        else:
            err_output = []
            if e.stderr: err_output.append(f"STDERR: {e.stderr}")
            if e.stdout: err_output.append(f"STDOUT: {e.stdout}")
            full_err = "\n".join(err_output) if err_output else f"Exit code: {e.returncode}"
            
            if e.returncode == 43:
                full_err += "\n\n[提示] Pandoc Exit Code 43 表明底层 PDF 渲染引擎 (LaTeX) 崩溃。如果文档包含中文、特殊公式或大量图片，原生 LaTeX 经常报错：\n1. 请确保系统中安装了完整的 LaTeX 环境（如 MiKTeX/TeXLive）。\n2. 如需处理中文，建议使用 xelatex ，可以尝试手动测试能否单独完成 MD 转 PDF。"
                
            raise RuntimeError(f"Pandoc 编译错误:\n{full_err}")
