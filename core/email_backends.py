from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPEmailBackend
from django.core.mail.utils import DNS_NAME


class CompatEmailBackend(DjangoSMTPEmailBackend):
    """SMTP backend compatible with Python 3.13 starttls signature."""

    def open(self):
        if self.connection:
            return False

        connection_params = {"local_hostname": DNS_NAME.get_fqdn()}
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout

        if self.use_ssl:
            connection_params.update(
                {
                    "keyfile": self.ssl_keyfile,
                    "certfile": self.ssl_certfile,
                }
            )

        try:
            try:
                self.connection = self.connection_class(
                    self.host, self.port, **connection_params
                )
            except TypeError:
                # Python 3.12+ drops keyfile/certfile kwargs.
                connection_params.pop("keyfile", None)
                connection_params.pop("certfile", None)
                self.connection = self.connection_class(
                    self.host, self.port, **connection_params
                )

            if not self.use_ssl and self.use_tls:
                try:
                    self.connection.starttls(
                        keyfile=self.ssl_keyfile, certfile=self.ssl_certfile
                    )
                except TypeError:
                    self.connection.starttls()

            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except OSError:
            if not self.fail_silently:
                raise
