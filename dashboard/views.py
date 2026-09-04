import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import (
    get_dashboard_stats,
    ALLOWED_CHART_DAY_OPTIONS,
    DEFAULT_CHART_DAYS,
    CHART_SERIES,
)

# Create your views here.

@login_required
def dashboard_home(request):
    chart_days = request.GET.get("days", DEFAULT_CHART_DAYS)
    try:
        chart_days = int(chart_days)
    except (TypeError, ValueError):
        chart_days = DEFAULT_CHART_DAYS

    stats = get_dashboard_stats(request.user, chart_days=chart_days)
    
    first_series_status = CHART_SERIES[0][0]
    chart_labels = [day.strftime("%b %d") for day, count in stats["events_by_status"][first_series_status]]
    
    chart_datasets = []
    for status, label, color in CHART_SERIES:
        values = [count for day, count in stats["events_by_status"][status]]
        chart_datasets.append({"label": label, "data": values, "borderColor": color})

    return render(request, "dashboard/home.html", {
        **stats,
        "chart_data_json": json.dumps({"labels": chart_labels, "datasets": chart_datasets}),
        "chart_day_options": ALLOWED_CHART_DAY_OPTIONS,
    })