from django.urls import path

from .public_api_v1 import matches, overview


urlpatterns = [
    path('api/publica/v1/<slug:tenant_slug>/visao-geral/', overview, name='public-api-v1-overview'),
    path('api/publica/v1/<slug:tenant_slug>/partidas/', matches, name='public-api-v1-matches'),
]
