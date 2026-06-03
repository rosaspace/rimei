from datetime import datetime, date, timedelta, time
import calendar

def parse_date(value):
    """解析日期字符串为 date 对象"""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

def clean_date(value):
    """清理日期值，返回 date 对象或 None"""
    if value in ["", None]:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

def get_week_range(base_date=None):
    """获取指定日期所在周的开始和结束日期"""
    if base_date is None:
        base_date = date.today()
    
    start_of_week = base_date - timedelta(days=base_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    return {
        'start': start_of_week,
        'end': end_of_week,
        'next_start': start_of_week + timedelta(days=7),
        'next_end': start_of_week + timedelta(days=13),
        'next2_start': start_of_week + timedelta(days=14),
        'next2_end': start_of_week + timedelta(days=20),
    }

def get_week_days(week_start_date):
    """获取一周的日期列表"""
    weekdays = []
    for i in range(7):
        weekday_date = week_start_date + timedelta(days=i)
        weekdays.append({
            'weekday': i,
            'name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][i],
            'date': weekday_date
        })
    return weekdays

def convert_to_time(work_time):
    """将各种格式的时间转换为 time 对象"""
    if isinstance(work_time, str):
        return datetime.strptime(work_time, '%H:%M').time()
    elif isinstance(work_time, datetime):
        return work_time.time()
    elif isinstance(work_time, time):
        return work_time
    else:
        return time(8, 0)  # 默认 8:00

def sort_by_date(entry, field_name):
    """按日期字段排序，处理 None 和字符串"""
    date_val = entry.get(field_name)
    if date_val is None:
        return datetime.min
    if isinstance(date_val, datetime):
        return date_val
    elif isinstance(date_val, date):
        return datetime.combine(date_val, time.min)
    return datetime.min

def month_workdays(dt):
    """
    计算指定年月中，周一到周五的工作日数量（不含周末）
    
    Args:
        dt: date 或 datetime 对象
    
    Returns:
        int: 工作日数量
    """
    if isinstance(dt, datetime):
        dt = dt.date()
    
    year = dt.year
    month = dt.month
    
    total_days = calendar.monthrange(year, month)[1]
    workdays = 0
    
    for day in range(1, total_days + 1):
        weekday = date(year, month, day).weekday()
        # weekday: 0=周一, ..., 6=周日，排除周六(5)和周日(6)
        if weekday < 5:
            workdays += 1
    
    return workdays