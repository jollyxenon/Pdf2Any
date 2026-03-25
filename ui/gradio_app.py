import gradio as gr
import sys
import threading
import queue
import time
import os
import string
import logging
from config import logger

class OutputStream:
    """拦截 stdout 并放置到队列中供 Gradio 渲染"""
    def __init__(self, q, is_error=False):
        self.q = q
        self.encoding = 'utf-8'
        self.is_error = is_error
        
    def write(self, text):
        if text.strip():
            prefix = "[ERROR] " if self.is_error and not text.startswith("[ERROR]") else ""
            self.q.put(prefix + text)
            
    def flush(self):
        pass

def get_drives():
    drives = []
    if os.name == 'nt':
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
    else:
        drives.append("/")
    return drives

def launch_gui(start_conversion_batch_fn):
    def convert_pdf_ui(input_files, output_dir_input, api_key, out_formats, pandoc_network, formula_mode):
        if not input_files:
            yield "未选择任何 PDF 文件！", None
            return
            
        if not out_formats:
            yield "未选择任何输出格式！", None
            return

        pdf_paths = [f.name for f in input_files]
        
        if output_dir_input and output_dir_input.strip():
            out_dir = output_dir_input.strip()
        else:
            out_dir = os.path.dirname(os.path.abspath(pdf_paths[0]))
            
        # 日志捕获队列
        log_queue = queue.Queue()
        
        # 将 logger 添加处理队列
        queue_handler = logging.StreamHandler(OutputStream(log_queue))
        queue_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(queue_handler)
        
        # 映射 UI 参数到 CLI
        network_val = "online" if pandoc_network == "联网 (Online)" else "offline"
        formula_val = "image" if formula_mode == "图片形式 (Image/WebTex)" else "text"
        
        # 用于存放结果或错误的容器
        result_container = {"error": None, "done": False}
        
        def worker():
            try:
                start_conversion_batch_fn(
                    input_pdfs=pdf_paths, 
                    output_dir=out_dir, 
                    format_types=out_formats,
                    pandoc_network=network_val, 
                    formula_mode=formula_val,
                    cli_api_key=api_key.strip() if api_key else ""
                )
            except Exception as e:
                result_container["error"] = str(e)
            finally:
                result_container["done"] = True
                
        # 启动后台转换线程
        thread = threading.Thread(target=worker)
        thread.start()
        
        logs = ""
        # 实时更新 UI 循环
        while not result_container["done"]:
            while not log_queue.empty():
                logs += log_queue.get() + "\n"
            yield logs, None
            time.sleep(0.5)

        # 捕获最后可能遗留的输出
        while not log_queue.empty():
            logs += log_queue.get() + "\n"

        logger.removeHandler(queue_handler)
        
        if result_container["error"]:
            logs += f"\n[ERROR] 批量任务异常停止: {result_container['error']}\n"
            yield logs, None
        else:
            logs += f"\n[SUCCESS] 所有的 PDF 处理完毕！\n"
            
            # 收集产生的文件列表反馈给前端UI
            generated_files = []
            for p in pdf_paths:
                base_name = os.path.splitext(os.path.basename(p))[0]
                for fmt in out_formats:
                    out_path = os.path.join(out_dir, f"{base_name}.{fmt}")
                    if os.path.exists(out_path):
                        generated_files.append(out_path)
                        
            if generated_files:
                yield logs, generated_files
            else:
                yield logs, None

    # ================= UI 设计 =================
    with gr.Blocks(title="PdfEpubConverter", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📚 PdfEpubConverter \n### 基于 MinerU 与 Pandoc 的高精度本地化强力批处理工具 (Plug & Play)")
        
        with gr.Row():
            with gr.Column(scale=1):
                pdf_input = gr.File(label="📄 上传 PDF 队列 (支持多选)", file_types=[".pdf"], file_count="multiple")
                out_dir_input = gr.Textbox(label="📁 设定输出文件夹绝对路径", placeholder="(可选) 留空则默认储存在第一个 PDF 文件同级目录下")
                
                with gr.Row():
                    out_format = gr.CheckboxGroup(
                        choices=["epub", "docx", "md", "tex", "pdf", "html"], 
                        value=["epub"], 
                        label="输出格式 (可多选，选PDF需本地装有LaTeX)"
                    )
                
                with gr.Row():
                    pandoc_network = gr.Radio(
                        choices=["离线 (Offline, 推荐)", "联网 (Online)"], 
                        value="离线 (Offline, 推荐)", 
                        label="Pandoc 联网验证"
                    )
                    formula_mode = gr.Radio(
                        choices=["文本形式 (MathML/原生LaTeX)", "图片形式 (Image/WebTex)"], 
                        value="文本形式 (MathML/原生LaTeX)", 
                        label="公式输出形式"
                    )
                    
                api_key_input = gr.Textbox(
                    label="MinerU API Key 补录 (可选留空)", 
                    placeholder="留空则自动读取 .env 的 MINERU_API_TOKEN", 
                    type="password"
                )
                convert_btn = gr.Button("🚀 加入队列并开始转换", variant="primary")
                
            with gr.Column(scale=1):
                file_output = gr.File(label="提取成功产生的文件")
                log_output = gr.Textbox(label="实时终端日志监控", lines=15, max_lines=20, interactive=False)

        convert_btn.click(
            fn=convert_pdf_ui,
            inputs=[pdf_input, out_dir_input, api_key_input, out_format, pandoc_network, formula_mode],
            outputs=[log_output, file_output]
        )

    demo.queue().launch(
        server_name="127.0.0.1", 
        inbrowser=True, 
        allowed_paths=get_drives()
    )
