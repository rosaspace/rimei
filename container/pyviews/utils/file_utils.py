import os
from django.conf import settings
from django.http import HttpResponse

def get_media_path(*path_parts):
    """构建 MEDIA_ROOT 下的文件路径"""
    return os.path.join(settings.MEDIA_ROOT, *path_parts)

def ensure_dir_exists(file_path):
    """确保文件所在目录存在"""
    dir_path = os.path.dirname(file_path)
    os.makedirs(dir_path, exist_ok=True)
    return file_path

def save_uploaded_file(uploaded_file, save_dir, filename=None):
    """保存上传的文件"""
    if filename is None:
        filename = uploaded_file.name
    
    ensure_dir_exists(os.path.join(save_dir, filename))
    file_path = os.path.join(save_dir, filename)
    
    with open(file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    return file_path

def serve_pdf_file(pdf_path, filename=None, inline=True):
    """读取 PDF 文件并返回 HttpResponse"""
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    if filename is None:
        filename = os.path.basename(pdf_path)
    
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        disposition = 'inline' if inline else 'attachment'
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        return response