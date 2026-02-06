import os
from django.http import HttpResponse

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader




def create_pdf_canvas(file_path, pagesize=letter):
    """
    创建 PDF Canvas，并确保目录存在
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    c = canvas.Canvas(file_path, pagesize=pagesize)

    return c, letter, inch, ImageReader


def finalize_pdf_and_response(
    canvas_obj,
    file_path,
    filename=None,
    content_type="application/pdf"
):
    """
    保存 PDF 并返回 HttpResponse
    """
    canvas_obj.save()

    if not filename:
        filename = os.path.basename(file_path)

    with open(file_path, "rb") as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response
