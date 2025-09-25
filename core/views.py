from django.http import JsonResponse

def test_api(request):
    return JsonResponse({"message": "Hello from Django backend!"})

def dashboard_metrics(request):
    data = {
        "metrics": [
            { "id": 1, "title": "Total Items", "value": "1,842", "trend": "up", "change": "12%" },
            { "id": 2, "title": "Active Orders", "value": "24", "trend": "neutral", "change": "2" },
            { "id": 3, "title": "Critical Alerts", "value": "5", "trend": "down", "change": "3" },
            { "id": 4, "title": "Storage Used", "value": "78%", "trend": "up", "change": "5%" }
        ]
    }
    return JsonResponse(data)
