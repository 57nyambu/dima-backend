from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("api/schema/", staff_member_required(SpectacularAPIView.as_view()), name="schema"),
    path("api/docs/swagger/", staff_member_required(SpectacularSwaggerView.as_view(url_name="schema")), name="swagger-ui"),
    path("api/docs/redoc/", staff_member_required(SpectacularRedocView.as_view(url_name="schema")), name="redoc"),
    path('admin/', admin.site.urls),
    #path('api/core/', include('apps.core.urls')),
    #path('', include('apps.core.urls')),
    path('api/v1/auth/', include('apps.accounts.urls.auth')),
    path('api/v1/user-mgt/', include('apps.accounts.urls.user_mgt')),
    path('api/v1/', include('apps.products.urls')),
    path('api/v1/business/', include('apps.business.urls')),
    path("api/marketplace/", include("apps.marketplace.urls")),
    #path('api/categories/', include('apps.products.urls.catg'))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
