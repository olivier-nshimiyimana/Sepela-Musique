from django.apps import AppConfig
import os


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        """
        Optional bootstrap for hosts without shell access (e.g. Render free tier).
        Creates or promotes an admin user when env vars are provided.
        """
        if os.environ.get('DJANGO_CREATE_SUPERUSER', '').lower() not in ('1', 'true', 'yes'):
            return

        email = (os.environ.get('DJANGO_SUPERUSER_EMAIL') or '').strip().lower()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD') or ''
        first_name = (os.environ.get('DJANGO_SUPERUSER_FIRST_NAME') or 'Admin').strip()
        last_name = (os.environ.get('DJANGO_SUPERUSER_LAST_NAME') or 'User').strip()

        if not email or not password:
            return

        try:
            from django.contrib.auth import get_user_model
            from django.db.utils import OperationalError, ProgrammingError

            User = get_user_model()
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first_name,
                    'last_name': last_name,
                },
            )
            changed = False
            if created or not user.check_password(password):
                user.set_password(password)
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if getattr(user, 'user_type', None) != 1:
                user.user_type = 1
                changed = True
            if changed:
                user.save()
        except (OperationalError, ProgrammingError):
            # DB might not be ready during initial migration phase.
            return
