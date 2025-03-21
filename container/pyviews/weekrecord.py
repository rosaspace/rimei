from datetime import datetime, timedelta,date,time
from ..models import ClockRecord,Employee
from django.utils import timezone
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
import pandas as pd
from django.http import HttpResponse
from openpyxl.styles import Border, Side, PatternFill, Alignment

def week_record(request):
    # 获取当前年份和周数
    current_date = timezone.now().date()
    current_year = current_date.year
    current_week = current_date.isocalendar()[1]
    last_week = current_week -1;

    # 计算上周的开始和结束日期
    last_week_start = current_date - timedelta(days=current_date.weekday() + 7)  # 上周的周一
    last_week_end = last_week_start + timedelta(days=6)  # 上周的周日
    print("hello: ",last_week_start,last_week_end)
    print("hello: ",last_week_start.year,last_week)
    print("hello: ",current_week)

    # 获取选定周的打卡记录
    weekly_records = ClockRecord.objects.filter(
        date__range=[last_week_start, last_week_end]
    )

    # 生成年份和周数选项
    current_year = timezone.now().year
    years = list(range(current_year, current_year + 1))  # 当前年份及前两年
    weeks = list(range(1, 53))  # 1-52周

    # 如果没有记录，返回空页面或消息
    if not weekly_records.exists():
        return render(request, 'container/weekrecord.html', {
            'records': [],
            'weekly_summary': None,  # 或者可以返回一个空的字典
            'years': years,
            'weeks': weeks,
            'selected_year': last_week_start.year,
            'selected_week': last_week
        })
    
    # 计算总工作时长
    total_hours = sum(record.total_hours for record in weekly_records)
    avg_hours = round(total_hours / 7, 2) if weekly_records else 0
    
    # 获取所有员工的周统计数据
    employees = Employee.objects.all()
    employee_records = []
    
    for employee in employees:
        employee_weekly_records = weekly_records.filter(employee_name=employee)
        employee_total_hours = sum(record.total_hours for record in employee_weekly_records)
        employee_avg_hours = round(employee_total_hours / 5, 2) if employee_weekly_records else 0
        employee_attendance_rate = round((employee_total_hours / 40) * 100, 2)
        
        # 只有当员工有打卡记录时才添加到列表中
        if employee_weekly_records.exists():
            employee_records.append({
                'id':employee.id,
                'name': employee.name,
                'period_start': last_week_start,
                'period_end': last_week_end,
                'total_hours': employee_total_hours,
                'average_hours': employee_avg_hours,
                "attendance_rate":employee_attendance_rate
            })   
    

    weekly_summary = {
        'total': total_hours,
        'average': avg_hours,        
        'employee_records': employee_records
    }
    
    return render(request, 'container/weekrecord.html', {
        'records': weekly_records,
        'weekly_summary': weekly_summary,
        'years': years,
        'weeks': weeks,
        'selected_year': last_week_start.year,
        'selected_week': last_week_start.isocalendar()[1]
    })

def add_week_records(request):
    today = timezone.now().date()
    current_week_start = today - timedelta(days=today.weekday())
    # 获取上周的周一日期
    last_week_start = current_week_start - timedelta(days=7)  # 上周的周一
    last_week_end = last_week_start + timedelta(days=6)  # 上周的周日
    print("hello: ",last_week_start,last_week_end)
    
    weekdays = getWeek(last_week_start)
    
    if request.method == 'POST':
        # 获取选择的员工名称
        name = request.POST.get('employee_name')
        print(f"Selected Employee Name: {name}")
        employee = Employee.objects.get(id=name)
        print(f"Selected Employee Name: {employee.name}")

        # 创建新的打卡记录
        # clock_record = ClockRecord(
        #     employee_name=employee,
        #     date=date.today(),  # 今天的日期
        #     weekday=date.today().weekday(),  # 自动获取星期几（0-6）
        #     morning_in="09:00",  # 可以直接使用字符串，save方法会自动转换
        #     morning_out="12:00",
        #     afternoon_in="13:00",
        #     afternoon_out="18:00"
        #     # evening_in 和 evening_out 是可选的，可以不填
        # )

        # # 保存到数据库
        # clock_record.save()
        
        for day in weekdays:
            # weekday = "Monday"
            weekdayname = day['name']
            weekday = day['weekday']
            date = day['date']            
            
            # 获取表单数据
            morning_in = request.POST.get(f'morning_in_{weekday}')
            morning_out = request.POST.get(f'morning_out_{weekday}')
            afternoon_in = request.POST.get(f'afternoon_in_{weekday}')
            afternoon_out = request.POST.get(f'afternoon_out_{weekday}')
            evening_in = request.POST.get(f'evening_in_{weekday}')
            evening_out = request.POST.get(f'evening_out_{weekday}')
            print("I am ok now\n", employee.name,date, weekdayname)
            print("Time: ",morning_in, morning_out, afternoon_in, afternoon_out, evening_in, evening_out )
            
            # 创建记录
            if any([morning_in, morning_out, afternoon_in, afternoon_out, evening_in, evening_out]):
                ClockRecord.objects.create(
                    date=date,
                    weekday=weekday,
                    employee_name=employee,
                    morning_in=morning_in or None,
                    morning_out=morning_out or None,
                    afternoon_in=afternoon_in or None,
                    afternoon_out=afternoon_out or None,
                    evening_in=evening_in or None,
                    evening_out=evening_out or None
                )
                # print("hello: ",type(wordrecord))
                # wordrecord.save()
                # return JsonResponse({"status": "success", "message": "Record added!"})
        
        return redirect('week_record')
    
    employees = Employee.objects.all()
    return render(request, 'container/weekrecord/add_record.html', {
        'weekdays': weekdays,
        'employees': employees,
    })

def edit_week_records(request, employee_id=None):
    today = timezone.now().date()
    current_week_start = today - timedelta(days=today.weekday())
    # 获取上周的周一日期
    last_week_start = current_week_start - timedelta(days=7)
    employee = Employee.objects.get(id=employee_id)  
    
    weekdays = getWeek(last_week_start)

    if request.method == 'POST':
        # Handle form submission to save work records
        for i in range(6):
            morning_in = request.POST.get(f'morning_in_{i}')
            morning_out = request.POST.get(f'morning_out_{i}')
            afternoon_in = request.POST.get(f'afternoon_in_{i}')
            afternoon_out = request.POST.get(f'afternoon_out_{i}')
            evening_in = request.POST.get(f'evening_in_{i}')
            evening_out = request.POST.get(f'evening_out_{i}')

            # Get weekday value from weekdays list
            weekday = weekdays[i]['weekday']
            date = last_week_start + timedelta(days=i)  # Calculate the date for the current weekday    
            print("hello: ",employee.name, weekdays[i]['name'], date)
            print("hello: ",morning_in,morning_out,afternoon_in,afternoon_out,evening_in,evening_out)
            
            # Save or update work records
            ClockRecord.objects.update_or_create(
                employee_name = employee,
                date = date,
                defaults={
                    'weekday': weekday,
                    'morning_in': morning_in or None,
                    'morning_out': morning_out or None,
                    'afternoon_in': afternoon_in or None,
                    'afternoon_out': afternoon_out or None,
                    'evening_in': evening_in or None,
                    'evening_out': evening_out or None,
                }
            )
            # 先检查是否存在记录
            # record, created = ClockRecord.objects.get_or_create(
            #     employee_name=employee,
            #     date=date,
            # )
            
            # # 直接更新字段
            # record.weekday = weekday
            # record.morning_in = morning_in if morning_in else record.morning_in
            # record.morning_out = morning_out if morning_out else record.morning_out
            # record.afternoon_in = afternoon_in if afternoon_in else record.afternoon_in
            # record.afternoon_out = afternoon_out if afternoon_out else record.afternoon_out
            # record.evening_in = evening_in if evening_in else record.evening_in
            # record.evening_out = evening_out if evening_out else record.evening_out
            # record.save()
        return redirect('week_record')

    current_employee = None
    work_records = []
    if employee_id:
        current_employee = Employee.objects.get(id=employee_id)
        work_records = ClockRecord.objects.filter(employee_name=current_employee, date__range=[last_week_start, last_week_start + timedelta(days=6)])
    
    work_record_dict = {record.date: record for record in work_records}

    return render(request, 'container/weekrecord/edit_record.html', {
        'weekdays': weekdays,
        'current_employee': current_employee,
        'work_records': work_record_dict,  # Pass the dictionary to the template
    })

def export_week_records(request):
    today = timezone.now().date()
    last_week_start = today - timedelta(days=today.weekday() + 7)  # 上周的周一
    last_week_end = last_week_start + timedelta(days=6)  # 上周的周日
    print("export working hours:", last_week_start, last_week_end)

    weekdays = getWeek(last_week_start)

    # 获取所有员工
    employees = Employee.objects.all()


    # 按照 belongTo 字段分组员工
    grouped_employees = {}
    for employee in employees:
        group = employee.belongTo  # 假设 belongTo 是一个字符串，表示员工所属的组
        if group not in grouped_employees:
            grouped_employees[group] = []
        grouped_employees[group].append(employee)

    # 定义颜色列表
    colors = ["FFFF99", "FFCCFF", "CCFFCC", "FFCCCC", "CCCCFF"]
    color_map = {}  # 用于存储每个员工的颜色

    # 为每个员工分配颜色
    for index, employee in enumerate(employees):
        color_map[employee.name] = colors[index % len(colors)]  # 循环使用颜色
        # print("color: ", employee.name, colors[index % len(colors)])

    # 存储所有响应
    responses = []

    # 为每个组创建一个工作表
    for group, group_employees in grouped_employees.items():
        print("---group: ",group)
        filename = f'Working_Hours_{group}_{last_week_start.strftime("%m.%d")}-{last_week_end.strftime("%m.%d")}.2025.xlsx'
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:

            data = []            

            for employee in group_employees:
                total_hours_weekly = 0
                employee_records = []
                # 获取该员工的上周打卡记录
                records = ClockRecord.objects.filter(employee_name=employee, date__range=[last_week_start, last_week_end])

                # 如果没有记录，跳过
                # if not records.exists():
                #     continue

                # 对记录按时间排序
                records = sorted(records, key=lambda r: (
                    r.date,  # 首先按日期排序
                    r.morning_in if r.morning_in else time(0, 0),  # 早上打卡时间
                    r.afternoon_in if r.afternoon_in else time(0, 0),  # 下午打卡时间
                    r.evening_in if r.evening_in else time(0, 0)  # 晚上打卡时间
                ))
                
                for record in records:
                    # 计算每天的工作时长
                    morning_in = record.morning_in
                    morning_out = record.morning_out
                    afternoon_in = record.afternoon_in
                    afternoon_out = record.afternoon_out
                    evening_in = record.evening_in
                    evening_out = record.evening_out
                    total_hours = record.total_hours
                    total_hours_weekly += total_hours

                    # 将 weekday 数字转换为字符串
                    weekday_str = weekdays[record.weekday]['name']

                    # 格式化时间，去掉秒
                    morning_in_str = morning_in.strftime('%H:%M') if morning_in else ''
                    morning_out_str = morning_out.strftime('%H:%M') if morning_out else ''
                    afternoon_in_str = afternoon_in.strftime('%H:%M') if afternoon_in else ''
                    afternoon_out_str = afternoon_out.strftime('%H:%M') if afternoon_out else ''
                    evening_in_str = evening_in.strftime('%H:%M') if evening_in else ''
                    evening_out_str = evening_out.strftime('%H:%M') if evening_out else ''

                    employee_records.append({
                        'Name': employee.name,
                        'Date': record.date,
                        'Weekday': weekday_str,
                        'In Time1': morning_in_str,
                        'Out Time1': morning_out_str,
                        'In Time2': afternoon_in_str,
                        'Out Time2': afternoon_out_str,
                        'In Time3': evening_in_str,
                        'Out Time3': evening_out_str,
                        'Total Hours Daily': total_hours,
                        "Total Hours Weekly": '',
                    })     
                # 在最后一条记录中添加周总时间
                if employee_records:
                    employee_records[-1]['Total Hours Weekly'] = total_hours_weekly 

                # 将该员工的所有记录添加到主数据列表
                data.extend(employee_records)                  
            if data:
                # 创建 DataFrame
                df = pd.DataFrame(data)

                # 将 DataFrame 写入 Excel 的一个工作表
                df.to_excel(writer, sheet_name=group, index=False)

                # 获取当前工作表
                worksheet = writer.sheets[group]

                # 设置列宽以适应内容
                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

                # 设置不同颜色和边框
                thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, min_col=1, max_col=len(data[0])):
                    for cell in row:
                        # 使用当前行员工的颜色
                        employee_id = data[row[0].row - 2]['Name']  # 获取当前行的员工名称
                        employee_color = color_map.get(employee_id)  # 获取该员工的颜色
                        # print("color2: ",employee_id, employee_color)
                        cell.fill = PatternFill(start_color=employee_color, end_color=employee_color, fill_type="solid")
                        cell.border = thin_border  # 添加边框
                        cell.alignment = Alignment(horizontal='center', vertical='center')  # 设置居中对齐

        # 返回 Excel 文件作为响应
        with open(filename, 'rb') as f:
            file_data = f.read()
            responses.append({
                'filename': filename,
                'data': file_data,
                'group': group
            })
    
    # 在循环结束后，根据请求参数返回特定的Excel文件
    group_param = request.GET.get('group')
    if group_param and responses:
        # 如果指定了组，返回该组的Excel
        for response in responses:
            if response['group'] == group_param:
                excel_response = HttpResponse(
                    response['data'],
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                excel_response['Content-Disposition'] = f'attachment; filename="{response["filename"]}"'
                return excel_response
    
    # 如果没有指定组或找不到指定组，返回第一个Excel
    if responses:
        excel_response = HttpResponse(
            responses[0]['data'],
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        excel_response['Content-Disposition'] = f'attachment; filename="{responses[0]["filename"]}"'
        return excel_response
    
    # 如果没有数据，返回空响应
    return HttpResponse("No data available for export.")

def convertToTime(workTime):
    if isinstance(workTime, str):
        print("Convert string to time")
        workTime = datetime.strptime(workTime, '%H:%M').time()  # Convert string to time object

    elif isinstance(workTime, datetime):
        print("Extract time from datetime")
        workTime = workTime.time()  # Extract only time from datetime object

    elif not isinstance(workTime, time):
        print("Set default time (08:00)")
        workTime = time(8, 0)  # Default to 8:00 AM if invalid

    return workTime

def getWeek(last_week_start):
    weekdays = []
    for i in range(6):  # Get all days of the week
        weekday_date = last_week_start + timedelta(days=i)
        weekdays.append({
            'weekday': i,
            'name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][i],
            'date': weekday_date
        })
    return weekdays