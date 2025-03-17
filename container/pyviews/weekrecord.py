from datetime import datetime, timedelta,date,time
from ..models import ClockRecord,Employee, ClockRecord
from django.utils import timezone
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.http import JsonResponse

def week_record(request):
    # 获取当前年份和周数
    current_date = timezone.now().date()
    current_year = current_date.year
    current_week = current_date.isocalendar()[1]

    # 从请求中获取选择的年份和周数
    selected_year = int(request.GET.get('year', current_year))
    selected_week = int(request.GET.get('week', current_week))

    # 根据选择的年份和周数计算日期范围
    first_day_of_week = datetime.strptime(f'{selected_year}-W{selected_week}-1', '%Y-W%W-%w').date()
    last_day_of_week = first_day_of_week + timedelta(days=6)

    # 获取选定周的打卡记录
    weekly_records = ClockRecord.objects.filter(
        date__range=[first_day_of_week, last_day_of_week]
    )
    
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
        
        employee_records.append({
            'id':employee.id,
            'name': employee.name,
            'period_start': first_day_of_week,
            'period_end': last_day_of_week,
            'total_hours': employee_total_hours,
            'average_hours': employee_avg_hours,
            "attendance_rate":employee_attendance_rate
        })
    
    # 生成年份和周数选项
    current_year = timezone.now().year
    years = list(range(current_year - 2, current_year + 1))  # 当前年份及前两年
    weeks = list(range(1, 53))  # 1-52周

    weekly_summary = {
        'total': total_hours,
        'average': avg_hours,
        'years': years,
        'weeks': weeks,
        'employee_records': employee_records
    }
    
    return render(request, 'container/weekrecord.html', {
        'records': weekly_records,
        'weekly_summary': weekly_summary,
        'selected_year': selected_year,
        'selected_week': selected_week
    })

def add_week_records(request):
    today = timezone.now().date()
    current_week_start = today - timedelta(days=today.weekday())
    # 获取上周的周一日期
    last_week_start = current_week_start - timedelta(days=7)
    
    weekdays = []
    for i in range(7):  # Get all days of the week
        weekday_date = last_week_start + timedelta(days=i)
        weekdays.append({
            'weekday': i,
            'name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][i],
            'date': weekday_date
        })
    
    if request.method == 'POST':
        # 获取选择的员工名称
        name = request.POST.get('employee_name')
        print(f"Selected Employee Name: {name}")
        employee = Employee.objects.get(id=name)        
        
        for day in weekdays:
            weekday = day['weekday']
            date = day['date']            
            
            # 获取表单数据
            morning_in = request.POST.get(f'morning_in_{weekday}')
            morning_out = request.POST.get(f'morning_out_{weekday}')
            afternoon_in = request.POST.get(f'afternoon_in_{weekday}')
            afternoon_out = request.POST.get(f'afternoon_out_{weekday}')
            evening_in = request.POST.get(f'evening_in_{weekday}')
            evening_out = request.POST.get(f'evening_out_{weekday}')
            
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
        
        return redirect('week_record')
    
    employees = Employee.objects.all()
    return render(request, 'container/weekrecord/add_record.html', {
        'weekdays': weekdays,
        'employees': employees,
    })

def edit_week_records(request, employee_id=None):
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())    
    employee = Employee.objects.get(id=employee_id)  
    
    weekdays = []
    for i in range(7):  # Get all days of the week
        weekday_date = week_start + timedelta(days=i)
        weekdays.append({
            'weekday': i,
            'name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][i],
            'date': weekday_date
        })

    if request.method == 'POST':
        # Handle form submission to save work records
        for i in range(7):
            morning_in = request.POST.get(f'morning_in_{i}')
            morning_out = request.POST.get(f'morning_out_{i}')
            afternoon_in = request.POST.get(f'afternoon_in_{i}')
            afternoon_out = request.POST.get(f'afternoon_out_{i}')
            evening_in = request.POST.get(f'evening_in_{i}')
            evening_out = request.POST.get(f'evening_out_{i}')

            # Get weekday value from weekdays list
            weekday = weekdays[i]['weekday']
            
            # Save or update work records
            ClockRecord.objects.update_or_create(
                employee_name=employee,
                date=week_start + timedelta(days=i),
                weekday=weekday,
                defaults={
                    'morning_in': morning_in or None,
                    'morning_out': morning_out or None,
                    'afternoon_in': afternoon_in or None,
                    'afternoon_out': afternoon_out or None,
                    'evening_in': evening_in or None,
                    'evening_out': evening_out or None,
                }
            )
        return redirect('week_record')

    current_employee = None
    work_records = []
    if employee_id:
        current_employee = Employee.objects.get(id=employee_id)
        work_records = ClockRecord.objects.filter(employee_name=current_employee, date__range=[week_start, week_start + timedelta(days=6)])
    
    work_record_dict = {record.date: record for record in work_records}

    return render(request, 'container/weekrecord/edit_record.html', {
        'weekdays': weekdays,
        'current_employee': current_employee,
        'work_records': work_record_dict,  # Pass the dictionary to the template
    })

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