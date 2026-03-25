import os
import requests
import time
import zipfile
from config import logger

class MinerUConverter:
    def __init__(self, api_keys: list):
        self.api_keys = [k for k in api_keys if k and k.strip()]
        if not self.api_keys:
            raise ValueError("未提供有效的 MinerU API Key。请在 .env 文件或界面中配置。")

    def parse(self, input_pdf: str, work_dir: str) -> str:
        """利用 MinerU API 进行解析，支持多 Token 轮查与中途配额耗尽重试"""
        file_name = os.path.basename(input_pdf)
        data = {"files": [{"name": file_name, "data_id": "pdfdoc"}], "model_version": "vlm"}
        
        for key in self.api_keys:
            try:
                logger.info(f"[*] 正在尝试 Token: {key[:8]}... (开始 MinerU 完整流程解析)")
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key.strip()}"
                }
                
                # 1. 申请链接
                batch_url_req = "https://mineru.net/api/v4/file-urls/batch"
                resp = requests.post(batch_url_req, headers=headers, json=data, timeout=30)
                if resp.status_code in [402, 403, 429]:
                    raise RuntimeError(f"HTTP {resp.status_code} (Token 限额或限制)")
                resp.raise_for_status()
                
                result = resp.json()
                if result.get("code") != 0:
                    raise RuntimeError(f"申请上传链接失败(可能限流/失效): {result.get('msg')}")
                    
                batch_id = result["data"]["batch_id"]
                upload_url = result["data"]["file_urls"][0]
                logger.info("[SUCCESS] Token 验证通过！连接建立。")
                
                # 2. 上传文件
                logger.info("[*] 正在上传 PDF 文件...")
                with open(input_pdf, "rb") as f:
                    res_upload = requests.put(upload_url, data=f, timeout=600)
                    if res_upload.status_code in [402, 403, 429]:
                        raise RuntimeError(f"上传阶段遇到限制 HTTP {res_upload.status_code}")
                    res_upload.raise_for_status()
                    
                # 3. 轮询结果
                logger.info(f"[*] 解析任务已提交 (batch: {batch_id})，等待云端处理...")
                poll_url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
                
                zip_url = None
                timeout = 1800  # 30分钟超时
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    res = requests.get(poll_url, headers=headers, timeout=30)
                    if res.status_code in [402, 403, 429]:
                        raise RuntimeError(f"轮询阶段遇到限制 HTTP {res.status_code}")
                    res.raise_for_status()
                    
                    poll_res = res.json()
                    if poll_res.get("code") != 0:
                        raise RuntimeError(f"查询状态失败: {poll_res.get('msg')}")
                        
                    extract_result = poll_res["data"]["extract_result"][0]
                    state = extract_result["state"]
                    
                    if state == "done":
                        zip_url = extract_result.get("full_zip_url")
                        if not zip_url:
                            raise RuntimeError("解析完成，但未返回压缩包地址。")
                        break
                    elif state == "failed":
                        err_msg = extract_result.get("err_msg", "未知错误")
                        raise RuntimeError(f"云端解析失败: {err_msg}")
                    
                    time.sleep(5)
                    
                if not zip_url:
                    raise RuntimeError(f"解析超时 ({timeout}s)")
                    
                # 4. 下载并落盘
                logger.info("[*] 解析成功，正在下载结果压缩包...")
                zip_path = os.path.join(work_dir, "result.zip")
                dl_resp = requests.get(zip_url, stream=True, timeout=600)
                dl_resp.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in dl_resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                logger.info("[*] 正在落盘并提取 Markdown 数据...")
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(work_dir)
                    
                md_file_path = None
                for root, _, files in os.walk(work_dir):
                    for file in files:
                        if file.endswith(".md"):
                            md_file_path = os.path.join(root, file)
                            break
                    if md_file_path:
                        break
                            
                if md_file_path is None:
                    raise RuntimeError("解析结果压缩包中未找到 Markdown 文件。")
                    
                return md_file_path
                
            except Exception as e:
                logger.warning(f"[-] 流程中发生异常/被限额 ({e})，将尝试下一个可用 Token...")
                continue
                
        raise RuntimeError("提供的所有 Token 均不可用、已达调用限额，或网络解析全部崩溃。")
