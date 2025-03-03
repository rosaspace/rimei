import os
import fitz  # PyMuPDF 解析 PDF
from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.storage import default_storage
from ..models import Container
from django.conf import settings

UPLOAD_DIR = "uploads/"

# PDF 解析函数
def extract_text_from_pdf(pdf_path):
    """ 解析 PDF 并提取文本 """
    full_path = os.path.join(settings.MEDIA_ROOT, pdf_path)  # 获取完整路径

    # ✅ 检查文件是否存在
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"PDF 文件未找到: {full_path}")
    print("hello: ",  full_path)

    doc = fitz.open(full_path)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    doc.close()
    return text.strip()

# 处理上传
def upload_pdf(request):
    if request.method == "POST" and request.FILES.get("pdf_file"):

        pdf_file = request.FILES["pdf_file"]

        upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")  # 确保路径在 MEDIA_ROOT 目录下

        # ✅ 如果目录不存在，则创建
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        file_path = os.path.join(UPLOAD_DIR, pdf_file.name)


        # 保存文件
        with default_storage.open(file_path, "wb+") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)


        # 解析 PDF
        extracted_text = extract_text_from_pdf(file_path)
        
        return JsonResponse({
            "message": "文件上传并解析成功",
            "file_path": file_path,
            "content": extracted_text[:500]  # 只返回部分文本，防止太长
        })

    return JsonResponse({"error": "Invalid request"}, status=400)

# 处理保存到数据库
def save_container(request):
    if request.method == "POST":
        file_name = request.POST.get("file_name")
        content = request.POST.get("content")

        if file_name and content:
            container = Container(file_name=file_name, content=content)
            container.save()
            return JsonResponse({"message": "保存成功", "id": container.id})
    
    return JsonResponse({"error": "数据错误"}, status=400)

# 渲染 container 页面
def container(request):
    return render(request, "container/container.html")
