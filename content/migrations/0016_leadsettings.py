from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0015_contentfeedblock_secondary_item_limit_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LeadSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='Настройки заявок', max_length=120, verbose_name='Название')),
                ('recipient_email', models.EmailField(blank=True, max_length=254, verbose_name='Email для заявок')),
                ('sender_name', models.CharField(blank=True, max_length=255, verbose_name='Подпись отправителя')),
                (
                    'success_message',
                    models.CharField(
                        blank=True,
                        default='Спасибо! Ваша заявка отправлена. Мы свяжемся с вами в ближайшее время.',
                        max_length=255,
                        verbose_name='Сообщение после отправки',
                    ),
                ),
                ('is_active', models.BooleanField(default=True, verbose_name='Активно')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Изменено')),
            ],
            options={
                'verbose_name': 'Настройки заявок',
                'verbose_name_plural': 'Настройки заявок',
            },
        ),
    ]
