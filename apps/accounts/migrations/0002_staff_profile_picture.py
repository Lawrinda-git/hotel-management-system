from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="staff",
            name="profile_picture",
            field=models.FileField(blank=True, null=True, upload_to="profile_pictures/"),
        ),
    ]
