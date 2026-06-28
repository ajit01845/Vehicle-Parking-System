# parking/context_processors.py
from django.conf import settings

def google_maps_key(request):
    """
    Google Maps API key ko har template me available karega
    """
    return {
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY
    }