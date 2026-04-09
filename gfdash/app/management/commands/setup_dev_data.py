import json
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.conf import settings

class Command(BaseCommand):
    help = 'システム必須グループ(Manager, Staff)の作成と、テストデータの投入を行います'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # 1. 必須グループの作成
        # superuserはDjango標準の属性で管理されるため、
        # 一般ユーザー向けの区分として「Manager」と「Staff」を作成します
        required_groups = ['Manager', 'Staff']
        for group_name in required_groups:
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Group "{group_name}" created'))

        # 2. JSONファイルの読み込み
        file_path = os.path.join(settings.BASE_DIR, 'dev_params.json')

        if not os.path.exists(file_path):
            self.stdout.write(self.style.NOTICE('Notice: dev_params.json がないため、テストユーザー作成をスキップします。'))
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for user_data in data.get('test_users', []):
                username = user_data.get('username')
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(
                        username=username,
                        email=user_data.get('email'),
                        password=user_data.get('password')
                    )
                    
                    # 指定されたグループ（Manager または Staff）に所属させる
                    target_group = user_data.get('group')
                    if target_group in required_groups:
                        group = Group.objects.get(name=target_group)
                        user.groups.add(group)
                        self.stdout.write(self.style.SUCCESS(f'User "{username}" created as {target_group}'))
                else:
                    self.stdout.write(f'User "{username}" already exists.')

        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR('Error: JSONファイルが壊れています。'))