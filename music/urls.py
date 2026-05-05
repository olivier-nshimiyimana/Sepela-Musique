from django.contrib import admin
from django.conf.urls.i18n import set_language
from django.urls import path, include
from django.views.generic.base import RedirectView

urlpatterns = [
    # Browser icon requests fallback to existing static logo asset.
    path('favicon.ico', RedirectView.as_view(url='/static/images/logos/sepelamusique.png', permanent=True)),
    path('favicon.png', RedirectView.as_view(url='/static/images/logos/sepelamusique.png', permanent=True)),
    path('apple-touch-icon.png', RedirectView.as_view(url='/static/images/logos/sepelamusique.png', permanent=True)),
    path('apple-touch-icon-precomposed.png', RedirectView.as_view(url='/static/images/logos/sepelamusique.png', permanent=True)),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('admin/', admin.site.urls),
    path('i18n/setlang/', set_language, name='set_language'),
]
