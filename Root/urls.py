from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls.auth')),
    path('api/v1/user-mgt/', include('apps.accounts.urls.user_mgt')),
    path('api/v1/', include('apps.products.urls')),
    #path('api/categories/', include('apps.products.urls.catg'))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
