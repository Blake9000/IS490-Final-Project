from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('resume_fixer', '0002_alter_resume_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='skill',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='skill',
            name='normalized_name',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.CreateModel(
            name='SkillAlias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('alias', models.CharField(max_length=255)),
                ('normalized_alias', models.CharField(db_index=True, max_length=255, unique=True)),
                ('source', models.CharField(default='manual', max_length=50)),
                ('skill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aliases', to='resume_fixer.skill')),
            ],
            options={
                'ordering': ['normalized_alias'],
            },
        ),
        migrations.AddIndex(
            model_name='skillalias',
            index=models.Index(fields=['normalized_alias'], name='resume_fixe_normali_0d5be3_idx'),
        ),
    ]