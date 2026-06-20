import argparse
import os
import re
import time
from datetime import datetime

import markdown
from playwright.sync_api import sync_playwright
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# 专业金融研报 CSS
REPORT_CSS = """
body {
    font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    line-height: 1.8;
    color: #2c3e50;
    padding: 0 40px;
    max-width: 860px;
    margin: 0 auto;
    background-color: white;
}

/* 品牌头部横幅 */
.brand-header {
    display: flex;
    align-items: center;
    padding: 12px 0;
    border-bottom: 2px solid #2563eb;
    margin-bottom: 20px;
}
.brand-logo {
    height: 48px;
    width: auto;
    flex-shrink: 0;
}
.brand-logo svg {
    height: 48px;
    width: auto;
}
.brand-date {
    margin-left: auto;
    font-size: 12px;
    color: #6b7280;
    flex-shrink: 0;
}

/* H1 报告标题 */
h1 {
    font-size: 22px;
    color: #1a1a2e;
    border-bottom: 2px solid #2563eb;
    padding-bottom: 8px;
    margin-top: 20px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
}

/* H2 个股标题 */
h2 {
    font-size: 18px;
    color: #1e40af;
    background: #f0f4ff;
    padding: 8px 12px;
    border-left: 4px solid #2563eb;
    border-bottom: none;
    border-radius: 0 4px 4px 0;
    margin-top: 30px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
    page-break-before: auto;
    page-break-after: avoid;
}

/* H3 章节标题 */
h3 {
    font-size: 15px;
    color: #374151;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 4px;
    margin-top: 20px;
    margin-bottom: 12px;
    font-weight: 600;
    line-height: 1.25;
    page-break-after: avoid;
}

/* H4-H6 */
h4, h5, h6 {
    margin-top: 16px;
    margin-bottom: 10px;
    font-weight: 600;
    line-height: 1.25;
    color: #374151;
    border-bottom: none;
}

/* 表格 */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin: 12px 0;
    page-break-inside: avoid;
}
table th {
    background: #1e40af;
    color: white;
    font-weight: 600;
    padding: 8px 12px;
    text-align: left;
}
table td {
    padding: 6px 12px;
    border-bottom: 1px solid #e5e7eb;
}
table tr:nth-child(even) {
    background: #f8fafc;
}

/* Blockquote */
blockquote {
    background: #f9fafb;
    border-left: 3px solid #9ca3af;
    padding: 8px 16px;
    color: #6b7280;
    font-size: 12px;
    margin: 12px 0;
    border-radius: 0 4px 4px 0;
}

/* 评级徽章 */
.badge-bull {
    background: #dcfce7;
    color: #166534;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
}
.badge-neutral {
    background: #f3f4f6;
    color: #374151;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
}
.badge-bear {
    background: #fee2e2;
    color: #991b1b;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
}

/* 分割线 */
hr {
    border: none;
    border-top: 1px dashed #d1d5db;
    margin: 24px 0;
}

/* 列表 */
ul, ol {
    padding-left: 20px;
}
li {
    margin-bottom: 4px;
}

/* 加粗文本 */
strong {
    color: #1e293b;
}

/* 分页控制 */
p {
    orphans: 3;
    widows: 3;
}

/* 底部免责 */
.footer {
    margin-top: 40px;
    text-align: center;
    font-size: 11px;
    color: #9ca3af;
    border-top: 1px solid #e5e7eb;
    padding-top: 12px;
}
"""


def _inject_rating_badges(html):
    """将评级关键词替换为彩色徽章"""
    patterns = [
        (r'<strong>看多</strong>', '<span class="badge-bull">看多</span>'),
        (r'<strong>中性偏多</strong>', '<span class="badge-bull">中性偏多</span>'),
        (r'<strong>中性</strong>', '<span class="badge-neutral">中性</span>'),
        (r'<strong>中性偏空</strong>', '<span class="badge-bear">中性偏空</span>'),
        (r'<strong>看空</strong>', '<span class="badge-bear">看空</span>'),
    ]
    for pattern, replacement in patterns:
        html = re.sub(pattern, replacement, html)
    return html


def _extract_report_date(md_content):
    """从 markdown 内容中提取报告日期"""
    match = re.search(r'(\d{4}-\d{2}-\d{2})', md_content)
    if match:
        return match.group(1)
    return datetime.now().strftime('%Y-%m-%d')


def md_to_pdf(md_path, pdf_path):
    # 如果 PDF 已存在且比 MD 新，则跳过
    if os.path.exists(pdf_path) and os.path.getmtime(pdf_path) > os.path.getmtime(md_path):
        return False

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 转换: {os.path.basename(md_path)}")

    with open(md_path, encoding='utf-8') as f:
        md_content = f.read()

    html_content = markdown.markdown(md_content, extensions=['extra', 'tables', 'toc'])

    # 评级徽章自动着色
    html_content = _inject_rating_badges(html_content)

    # 提取报告日期
    report_date = _extract_report_date(md_content)

    # 加载 SVG logo
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'logo_banner.svg')
    try:
        with open(logo_path, encoding='utf-8') as f:
            logo_svg = f.read()
    except FileNotFoundError:
        logo_svg = '<span style="font-size:18px;font-weight:700;color:#1e40af;">量知 AIpha</span>'

    # 品牌头部横幅
    brand_header = f'''<div class="brand-header">
    <div class="brand-logo">{logo_svg}</div>
    <span class="brand-date">{report_date}</span>
</div>'''

    # 底部免责声明
    footer_div = f'<div class="footer">量知 AIpha | QuantZ AIpha | {datetime.now().strftime("%Y-%m-%d %H:%M")}<br>本报告由AI基于公开数据自动生成，仅供学习参考，不构成投资建议</div>'

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>{REPORT_CSS}</style>
</head>
<body>
    {brand_header}
    {html_content}
    {footer_div}
</body>
</html>"""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(full_html)
            page.wait_for_load_state("networkidle")
            page.pdf(
                path=pdf_path,
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template='''
                    <div style="font-size:9px; color:#9ca3af; width:100%; padding:0 40px; display:flex; justify-content:space-between;">
                        <span>量知 AIpha | QuantZ AIpha</span>
                        <span class="date"></span>
                    </div>
                ''',
                footer_template='''
                    <div style="font-size:9px; color:#9ca3af; width:100%; padding:0 40px; display:flex; justify-content:space-between;">
                        <span>仅供学习参考，不构成投资建议</span>
                        <span>第 <span class="pageNumber"></span> / <span class="totalPages"></span> 页</span>
                    </div>
                ''',
                margin={"top": "25mm", "bottom": "20mm", "left": "20mm", "right": "20mm"}
            )
            browser.close()
        return True
    except Exception as e:
        print(f"转换出错 {md_path}: {e}")
        return False

class MarkdownHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            self.process(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith(".md"):
            self.process(event.dest_path)

    def process(self, md_path):
        # 稍等片刻，确保文件写入完成
        time.sleep(1)
        pdf_path = md_path.replace(".md", ".pdf")
        md_to_pdf(md_path, pdf_path)

def initial_scan(root_dir):
    print(f"正在扫描目录: {root_dir} ...")
    count = 0
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".md"):
                md_path = os.path.join(root, file)
                pdf_path = md_path.replace(".md", ".pdf")
                if md_to_pdf(md_path, pdf_path):
                    count += 1
    print(f"初始化完成，转换了 {count} 个新文件。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto MD to PDF Watcher")
    parser.add_argument("--dir", default="Report", help="监控的目录路径")
    args = parser.parse_args()

    report_dir = os.path.abspath(args.dir)
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    # 1. 初始扫描
    initial_scan(report_dir)

    # 2. 启动监控
    event_handler = MarkdownHandler()
    observer = Observer()
    observer.schedule(event_handler, report_dir, recursive=True)

    print(f"\n正在监控目录: {report_dir}")
    print("一旦有新的 .md 文件生成，将自动转换。按 Ctrl+C 停止。")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
