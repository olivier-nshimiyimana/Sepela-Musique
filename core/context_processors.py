from .models import SiteConfiguration, SiteSettings


def site_settings(request):
    cfg = SiteConfiguration.get_solo()
    return {
        'site_settings': SiteSettings.get_solo(),
        'site_configuration': cfg,
        'SITE_MODE': cfg.mode,
        'SITE_MODE_IS_MISS_KATANGA': cfg.mode == SiteConfiguration.Mode.MISS_KATANGA,
    }
