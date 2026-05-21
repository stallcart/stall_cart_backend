"""
URL configuration for stall_cart project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from common.views import custom_404, custom_403, custom_500, custom_400,firebase_sw
from django.views.static import serve

handler404 = 'common.views.custom_404'
handler403 = 'common.views.custom_403'
handler500 ='common.views.custom_500'
handler400 = 'common.views.custom_400'
urlpatterns = [

    path('admin/', admin.site.urls),
    path('', include('shop.urls')),           # Main shop
    path('accounts/', include('accounts.urls')), # Auth
    path('orders/', include('orders.urls')),   # Orders
    path('delivery/', include('delivery.urls')), # ← Delivery app (this file)
    path('blog/', include('blog.urls')),       # Blog
    path('items/', include('items.urls')),     # Products
    path('common/', include('common.urls')),   
    path('firebase-messaging-sw.js', firebase_sw, name='firebase_sw'),


]


# ✅ Register custom error handlers


# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)