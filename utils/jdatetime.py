# Third Party Packages
from jdatetime import datetime as jalali_datetime
from django.utils.translation import gettext_lazy as _
from datetime import datetime, date, time
from django.utils import timezone
import pytz

months = ('فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
              'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند')
    
weekdays = ('دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه', 'یکشنبه')

def get_tehran_timezone():
    return pytz.timezone('Asia/Tehran')

def convert_to_jalali(instance):
    """Convert date or datetime to Jalali with Tehran timezone"""
    if isinstance(instance, datetime):
        dt = instance
    elif isinstance(instance, date):
        dt = datetime.combine(instance, time(0, 0))
    else:
        raise ValueError('convert_to_jalali expects date or datetime')

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, get_tehran_timezone())
    tehran_time = dt.astimezone(get_tehran_timezone())
    return jalali_datetime.fromgregorian(datetime=tehran_time)

def standard_jalali_date_format_safe(instance):
    """Safe date formatting that handles both date and datetime objects"""
    if isinstance(instance, date):
        jalali_date = jalali_datetime.fromgregorian(date=instance)
        return jalali_date.strftime('%Y/%m/%d')
    else:
        return convert_to_jalali(instance).strftime('%Y/%m/%d')

def standard_jalali_datetime_format(instance):
    return convert_to_jalali(instance).strftime('%H:%M %Y/%m/%d')

def standard_jalali_date_format(instance):
    return convert_to_jalali(instance).strftime('%Y/%m/%d')

def pretty_jalali_datetime_format(instance):
    _instance = convert_to_jalali(instance)
    months = ('فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند')
    return _instance.strftime('%d {} %Y'.format(months[int(_instance.strftime('%m')) - 1]))

def pretty_jalali_datetime_format_with_time(instance):
    """Format datetime in Jalali with Tehran timezone"""
    _instance = convert_to_jalali(instance)
    months = ('فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند')
    return _instance.strftime('%d {} %Y ساعت %H:%M'.format(months[int(_instance.strftime('%m')) - 1]))

def pretty_jalali_date_and_time_format(date, time):
    """Format date and time in Jalali with weekday and Tehran timezone"""
    date_time_instance = datetime.combine(date, time)
    _instance = convert_to_jalali(date_time_instance)
        
    weekday = weekdays[_instance.weekday()]
    month = months[int(_instance.strftime('%m')) - 1]
    
    return _instance.strftime(f'{weekday} %d {month} %Y ساعت %H:%M')

def pretty_jalali_date_format(date):
    """Format date in Jalali with Tehran timezone"""
    _instance = convert_to_jalali(date)
    weekday = weekdays[_instance.weekday()]
    month = months[int(_instance.strftime('%m')) - 1]
    return _instance.strftime(f'{weekday} %d {month} %Y')

def pretty_jalali_time_format(instance):
    """Format time (or datetime) in HH:MM with Tehran timezone consideration for datetimes"""
    return instance.strftime('%H:%M')

def humanize_datetime(instance):
    """
    Translates datetime values into verbal phrases with timezone support
    """
    if isinstance(instance, datetime):
        if timezone.is_naive(instance):
            instance = timezone.make_aware(instance)

        now = timezone.now()
        difference = now - instance

        days_past = difference.days
        seconds_past = difference.seconds

        if days_past == 0:
            if seconds_past < 10:
                return _('چند لحظه قبل')
            if seconds_past < 60:
                return '{0} {1}'.format(int(seconds_past), _('ثانیه قبل'))
            if seconds_past < 120:
                return _('یک دقیقه قبل')
            if seconds_past < 3600:
                return '{0} {1}'.format(int(seconds_past / 60), _('دقیقه قبل'))
            if seconds_past < 7200:
                return _('یک ساعت قبل')
            if seconds_past < 86400:
                return '{0} {1}'.format(int(seconds_past / 3600), _('ساعت قبل'))
        if days_past == 1:
            return _('دیروز')
        if days_past < 7:
            return '{0} {1}'.format(int(days_past), _('روز قبل'))
        if days_past < 31:
            return '{0} {1}'.format(int(days_past / 7), _('هفته قبل'))
        if days_past < 365:
            return '{0} {1}'.format(int(days_past / 30), _('ماه قبل'))
        return '{0} {1}'.format(int(days_past / 365), _('سال قبل'))
    else:
        raise ValueError('Enter standard datetime instance with timezone.')

def humanize_and_pretty_jalali_datetime(instance):
    return f'{humanize_datetime(instance)} | {pretty_jalali_datetime_format_with_time(instance)}'
