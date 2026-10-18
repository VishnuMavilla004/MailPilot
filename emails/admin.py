# Register your models here.
from django.contrib import admin
from .models import Email, Draft, Meeting, AIUsageLog
admin.site.register([Email, Draft, Meeting, AIUsageLog])