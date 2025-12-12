from django.http import HttpResponse
from django.views.decorators.http import require_GET

@require_GET
def health_check(request):
    """Endpoint de health check pour Render"""
    return HttpResponse("OK", status=200)