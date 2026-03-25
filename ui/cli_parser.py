import argparse

def get_parser():
    parser = argparse.ArgumentParser(description="PdfEpubOnlineConverter Batch CLI Tool")
    parser.add_argument("-i", "--input", nargs="+", help="输入的 PDF 文件路径，可同时提供多个")
    parser.add_argument("-o", "--output", help="输出的文件夹路径 (如不存在则自动创建)")
    parser.add_argument("-f", "--format", nargs="+", choices=["epub", "docx", "md", "tex", "pdf", "html"], default=["epub"], help="输出格式，可同时选多个 (e.g. -f epub md)")
    parser.add_argument("--network", choices=["online", "offline"], default="offline", help="Pandoc 联网模式 (决定公式与外界图片的拉取)")
    parser.add_argument("--formula", choices=["image", "text"], default="text", help="公式转义形式 (image 强制引入 webtex)")
    parser.add_argument("--api-key", default="", help="MinerU API Key，留空则自动读取 .env")
    return parser
