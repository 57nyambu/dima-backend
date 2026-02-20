from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.core.sitemaps import sitemaps

urlpatterns = [
    # SEO URLs
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    
    # API Documentation
    path("api/schema/", staff_member_required(SpectacularAPIView.as_view()), name="schema"),
    path("api/docs/swagger/", staff_member_required(SpectacularSwaggerView.as_view(url_name="schema")), name="swagger-ui"),
    path("api/docs/redoc/", staff_member_required(SpectacularRedocView.as_view(url_name="schema")), name="redoc"),
    #path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    #path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    #path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    
    # Admin
    path('admin/', admin.site.urls),

    # Dashboard
    path('api/v1/dashboard/', include('apps.dashboard.urls')),
    
    # API Endpoints
    path('api/v1/auth/', include('apps.accounts.urls.auth')),
    path('api/auth/', include('apps.accounts.urls.auth')),  # Non-versioned route (Google OAuth redirects)
    path('api/v1/user-mgt/', include('apps.accounts.urls.user_mgt')),
    path('api/v1/', include('apps.products.urls')),
    path('api/v1/business/', include('apps.business.urls')),
    path("api/marketplace/", include("apps.marketplace.urls")),
    path("api/v1/shipping/", include("apps.shipping.urls")),
    path("api/v1/orders/", include("apps.orders.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
