import tempfile
import os

def create_temp_pdf():
    """
    创建临时 PDF 文件，返回文件路径
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_path = temp_file.name
    temp_file.close()
    return temp_path


def cleanup_temp_file(path):
    if path and os.path.exists(path):
        os.remove(path)