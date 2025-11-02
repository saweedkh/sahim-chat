# Django Packages
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

# Third Party Packages
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


api_v1_urlpatterns = [

    # Schema
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Account
    path('account/', include('account.urls')),
    path('chat/', include('chat.urls')),
]


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(api_v1_urlpatterns)),
]

# Serve static and media files
# In DEBUG mode, serve static files through Django
# In production, use a web server like Nginx
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # In production, only serve media files (static files should be served by web server)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
