import os
import fitz  # PyMuPDF 解析 PDF
from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.storage import default_storage
from ..models import Container
from django.conf import settings
from django.utils import timezone

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

# 打开添加Container页面
def add_container_view(request):
    """显示添加Container的页面"""
    return render(request, 'container/containerManager/add_container.html')

# 新增Container
def add_container(request):
    """处理添加Container的API请求"""
    print("----------add_container-----------")
    if request.method == 'POST':
        try:
            # 获取基本字段
            container_id = request.POST.get('container_id')
            pickup_number = request.POST.get('pickup_number')
            
            # 创建新的Container实例
            container = Container(
                container_id=container_id,
                pickup_number=pickup_number,
                created_at=timezone.now()
            )
            
            # 处理日期字段
            date_fields = ['railway_date', 'pickup_date', 'delivery_date', 'empty_date']
            for field in date_fields:
                value = request.POST.get(field)
                if value:
                    parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
                    setattr(container, field, parsed_date)
            
            # 处理PDF文件
            if 'container_pdf' in request.FILES:
                container.container_pdf = request.FILES['container_pdf']
                container.container_pdfname = request.FILES['container_pdf'].name
            
            container.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Container saved successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# 修改Container
def save_container(request):
    print("----------save_container-----------")
    if request.method == 'POST':
        try:
            container_id = request.POST.get('container_id')
            pickup_number = request.POST.get('pickup_number')
            
            # 创建新的 Container 记录
            container = Container(
                container_id=container_id,
                pickup_number=pickup_number,
                created_at=timezone.now()
            )
            
            # 如果上传了 PDF 文件
            if 'container_pdf' in request.FILES:
                container.container_pdf = request.FILES['container_pdf']
                container.container_pdfname = request.FILES['container_pdf'].name
            
            container.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Container saved successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)
