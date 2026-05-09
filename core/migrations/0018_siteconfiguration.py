from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_voterequest_payment_method"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteConfiguration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("MISS_KATANGA", "Miss Katanga"),
                            ("ART_COMPETITION", "Art competition"),
                        ],
                        default="ART_COMPETITION",
                        help_text="Switches public wording (Artist vs Candidate, song vs contestant, etc.).",
                        max_length=32,
                    ),
                ),
            ],
            options={
                "verbose_name": "Site configuration",
                "verbose_name_plural": "Site configuration",
            },
        ),
    ]
