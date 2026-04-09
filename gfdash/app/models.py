from __future__ import unicode_literals

from django.db import models
from django.utils import timezone

# Create your models here.

class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'

class Ta215Attnd(models.Model):
    business_day = models.DateField(primary_key=True, verbose_name="営業日")
    early_morn = models.IntegerField(default=0, verbose_name="早朝")
    morning = models.IntegerField(default=0, verbose_name="午前")
    afternoon = models.IntegerField(default=0, verbose_name="日中")
    night = models.IntegerField(default=0, verbose_name="夜間")
    late_night = models.IntegerField(default=0, verbose_name="深夜")
    member = models.IntegerField(default=0, verbose_name="会員")
    visitor = models.IntegerField(default=0, verbose_name="ビジター")
    int_school = models.IntegerField(default=0, verbose_name="内部スクール")
    ext_school = models.IntegerField(default=0, verbose_name="外部スクール")
    school_total = models.IntegerField(default=0, verbose_name="スクール合計")

    class Meta:
        managed = False
        db_table = 'ta215_attnd'
        verbose_name = '来場統計メイン'

class Ta216AttndAttr(models.Model):
    business_day = models.DateField(verbose_name="営業日")
    attr_name = models.CharField(max_length=50, verbose_name="属性名")
    val = models.IntegerField(default=0, verbose_name="数値")

    class Meta:
        managed = False
        db_table = 'ta216_attnd_attr'
        verbose_name = '拡張来場属性'
        constraints = [
            models.UniqueConstraint(fields=['business_day', 'attr_name'], name='unique_attnd_attr')
        ]

class Ta220Memo(models.Model):
    business_day = models.DateField(primary_key=True, verbose_name="営業日")
    holiday_flg = models.BooleanField(default=False, verbose_name="祝日フラグ")
    tokubetu_flg = models.BooleanField(default=False, verbose_name="特別営業フラグ")
    closed_flg = models.BooleanField(default=False, verbose_name="休業フラグ")
    temp_closed = models.IntegerField(default=0, verbose_name="時間休業フラグ")
    memo = models.CharField(max_length=255, blank=True, null=True, verbose_name="備考")
    input_date = models.DateField(auto_now_add=True, verbose_name="入力日")

    class Meta:
        managed = False
        db_table = 'ta220_memo'
        verbose_name = '日次備考情報'

class Tb120Report(models.Model):
    business_day = models.DateField(primary_key=True)
    aridaka = models.IntegerField(blank=True, null=True)
    nyukin = models.IntegerField(blank=True, null=True)
    shukkin = models.IntegerField(blank=True, null=True)
    sagaku = models.IntegerField(blank=True, null=True)
    ken = models.IntegerField(blank=True, null=True)
    school = models.IntegerField(blank=True, null=True)
    shop = models.IntegerField(blank=True, null=True)
    input_date = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb120_report'

class Tb330SalesDiff(models.Model):
    diff_date = models.DateField(primary_key=True)
    diff_sales = models.IntegerField(blank=True, null=True)
    diff_time_flg = models.IntegerField(blank=True, null=True)
    input_date = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb330_sales_diff'


class Tz101WeatherReport(models.Model):
    # 'weather_day' を主キーとして設定
    weather_day = models.DateField(primary_key=True, verbose_name="日付")

    # 気温関連のフィールド
    temp_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="最高気温")
    temp_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="最低気温")
    temp_ave = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="平均気温")

    # 降水関連のフィールド
    rainfall_hour_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="降水量（１０分間最大）")

    # 風関連のフィールド
    wind_max_speed = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="日最風速")
    wind_max_direction = models.CharField(max_length=255, null=True)
    wind_max_inst = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="日最大瞬間風速")
    wind_max_inst_dir = models.CharField(max_length=255, null=True)

    # 天気概況
    gaikyo = models.CharField(max_length=255, null=True)
    gaikyo_night = models.CharField(max_length=255, null=True)

    # input_dateはDateTimeFieldに変更し、自動更新するように設定
    input_date = models.DateTimeField(default=timezone.now, verbose_name="登録・更新日時")

    def __str__(self):
        return str(self.weather_day)

    class Meta:
        # PostgreSQLのスキーマとテーブル名を指定
        managed = False
        db_table = 'tz101_weather_report'
        verbose_name = "気象データ"
        verbose_name_plural = "気象データ"

    # 保存時にinput_dateを現在日時に更新
    def save(self, *args, **kwargs):
        self.input_date = timezone.now()
        super().save(*args, **kwargs)

class Tz105DetailedWeatherReport(models.Model):
    weather_day = models.DateField(verbose_name="年月日")
    weather_time = models.IntegerField(verbose_name="時")
    temp = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    rainfall = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    wind_speed = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    wind_direction = models.CharField(max_length=255, null=True)
    weather_num = models.IntegerField(null=True)  # オリジナルの数値を保存
    input_date = models.DateField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'gf"."tz105_detailed_weather_info'
        unique_together = (('weather_day', 'weather_time'),)

class Tz102WeatherAvarage(models.Model):
    weather_mmdd = models.CharField(primary_key=True, max_length=4)
    weather_mm = models.IntegerField(blank=False, null=False)
    weather_dd = models.IntegerField(blank=False, null=False)
    temp_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="最高気温")
    temp_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="最低気温")
    temp_ave = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="平均気温")

    class Meta:
        managed = False
        db_table = 'tz102_weather_avarage'

class Tz201DeptReport(models.Model):
    business_day = models.DateField(primary_key=True)
    code = models.IntegerField(blank=True, null=True)
    num = models.IntegerField(blank=True, null=True)
    sales = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tz201_dept_report'

class Tz202ClerkReport(models.Model):
    business_day = models.DateField(primary_key=True)
    code = models.IntegerField(blank=True, null=True)
    trans_num = models.IntegerField(blank=True, null=True)
    sales_num = models.IntegerField(blank=True, null=True)
    sales = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tz202_clerk_report'

class Tz901ComName(models.Model):
    code = models.IntegerField(primary_key=True)
    num = models.IntegerField(blank=False, null=False)
    code_name = models.CharField(max_length=255, blank=True, null=True)
    code_name2 = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tz901_com_name'

class Tz910Permission(models.Model):
    template_name = models.CharField(max_length=100, primary_key=True)
    required_level = models.IntegerField(default=0)
    memo = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = 'tz910_permission'
        managed = False  # ※SQLで直接テーブルを作った場合は False にしておきます