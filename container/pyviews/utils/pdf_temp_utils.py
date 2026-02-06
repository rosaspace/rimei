import tempfile
import os

from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import letter

def create_temp_pdf(elements):
    """
    创建临时 PDF 文件，返回文件路径
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_path = temp_file.name
    temp_file.close()

    # ✅ 使用 ReportLab 写入该 PDF 文件
    doc = SimpleDocTemplate(temp_path, pagesize=letter, rightMargin=46, leftMargin=46, topMargin=60, bottomMargin=30)
    doc.build(elements)

    return temp_path


def cleanup_temp_file(path):
    if path and os.path.exists(path):
        os.remove(path)