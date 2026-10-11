# app/views/view_000global.py
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.http.response import HttpResponseBase
from django.conf import settings
from .. import views
from django.views import View
import json
from django.http.response import JsonResponse
from django.urls import path
from pathlib import Path
import codecs
import os

# ▼ 設定クラスの読み込み
from .config_custom import CustomSystemConfig as Config
# ▼ モデルの読み込み
from ..models import Tz910Permission
from ..utils.com_utils import com_get_half_year_info

from pathlib import Path  # ファイルの先頭でインポートしてください

# ▼ メインのHTMLレンダリング関数
def gentella_html(request):
    
    is_sample = getattr(settings, 'IS_SAMPLE_MODE', False)

    # 【重要】サンプルモードOFF なのに「未ログイン」の場合はログイン画面へ飛ばす！
    # ログインなしのモード（ANONYMOUS_LEVEL）では、未ログインのまま権限判定へ進む
    if not is_sample and not request.user.is_authenticated and sub_anonymous_level() is None:
        # ※ログインURLが異なる場合は '/login/' の部分を変更してください
        return redirect('/login/')
    
    load_template = request.path.split('/')[-1]

    # 1. エイリアスの解決（'' や 'index.html' を '001dashbord.html' に変換）
    if load_template in Config.TEMPLATE_ALIASES:
        load_template = Config.TEMPLATE_ALIASES[load_template]

    match request.method:
        case 'GET':
            # 権限チェックはデモンストレーションモードでも行う。has_permission は
            # デモではメンテナンス系(9xx)を拒否し、それ以外を許す。以前はデモのとき
            # 呼んでいなかったため、9xx はメニューから隠れているだけで、URL を
            # 直接開けば表示も保存もできた
            if not has_permission(request.user, load_template):
                return render(request, 'app/page_403.html', status=403)

            # 2. 解決済みの load_template を get_request に渡す
            ctx = get_request(request, load_template)
            
            # テンプレート側（HTML）でも分岐できるように変数を渡す
            ctx['is_sample_mode'] = is_sample
            # 権限の段階（-1〜2）。ログインなしのモードでは未ログインでも段階を持つので、
            # テンプレートは is_superuser ではなくこれで出し分ける
            ctx['user_level'] = get_user_level(request.user)
            # ログインなしのモードで、未ログインのまま使っているか（ログアウト等を出さない）
            ctx['is_anonymous_mode'] = (not request.user.is_authenticated
                                        and sub_anonymous_level() is not None)
            # Configからタイトルを取得
            ctx['page_title'] = Config.PAGE_META_DATA.get(load_template, '')
            # 上期・下期の期間設定。グラフのX軸ラベルや凡例で使うため全画面へ渡す
            ctx['half_year_info_json'] = json.dumps(com_get_half_year_info(), ensure_ascii=False)
            return render(request, 'app/' + ctx['load_template'], ctx)
            
        case 'POST':
            # GET と同じく、デモンストレーションモードでも権限チェックを行う
            if not has_permission(request.user, load_template):
                return render(request, 'app/page_403.html', status=403)

            # デモンストレーションモードでは更新させない。許可リストにある画面は、
            # 読み取りの操作だけを通す（既定で拒否）
            if is_sample and not sub_sample_post_allowed(request, load_template):
                return HttpResponse(json.dumps({
                    'demo_blocked': True,
                    'err_message': 'デモンストレーションモードでは、データの変更はできません。',
                }, ensure_ascii=False), content_type='application/json')

            # 3. 解決済みの load_template を post_request に渡す
            json_ret = post_request(request, load_template)

            # view が応答そのものを返した場合は包み直さない。
            #
            # HttpResponse(StreamingHttpResponse) は中身を最後まで読み切って
            # 1つの本文にまとめてしまう。バッチの実行ログを少しずつ流すために
            # StreamingHttpResponse を使っているのに、包み直した時点で
            # 全部終わってからまとめて届く応答になっていた。
            if isinstance(json_ret, HttpResponseBase):
                return json_ret

            return HttpResponse(json_ret, content_type='application/json')

# ▼ GET時の処理
def get_request(request, load_template):
    ctx = {}
    ctx['load_template'] = load_template

    # 未知のページ（Configに存在しないHTML）は 404 にルーティング
    if load_template not in Config.PAGE_META_DATA and load_template != 'page_404.html':
        ctx['load_template'] = "page_404.html"
        return ctx

    # ConfigからGETルーティングを取得
    routes = Config.get_get_routes(views)
    
    # 特別な処理があれば実行
    func = routes.get(load_template)
    if callable(func):
        ctx = func(ctx)
        
    return ctx

# ▼ POST時の処理
def post_request(request, load_template):
    # ConfigからPOSTルーティングを取得
    routes = Config.get_post_routes(views)
    
    func = routes.get(load_template)
    if callable(func):
        return func(request)
        
    return json.dumps({'error': f'View function for {load_template} is not defined'}, ensure_ascii=False)

def sub_anonymous_level():
    """ログインなしのモードの権限（0〜2）。無効なら None。デモモードが優先"""
    if getattr(settings, 'IS_SAMPLE_MODE', False):
        return None
    return getattr(settings, 'ANONYMOUS_LEVEL', None)


def sub_sample_post_allowed(pRequest, pTemplate):
    """
    デモンストレーションモードで、この POST を通してよいか。

    SAMPLE_MODE_READ_MODES に載った画面は、載っている操作（getMode）だけを通す。
    載っていない画面は通す（読み取りだけの画面）。メンテナンス系(9xx)は
    has_permission が画面ごと拒否する。
    """
    from django.http import QueryDict
    allowed = Config.SAMPLE_MODE_READ_MODES.get(pTemplate)
    if allowed is None:
        return True
    mode = QueryDict(pRequest.body, encoding='utf-8').get('getMode')
    return mode in allowed


class gentella_upload(View):
    def post(self, request, *args, **kwargs):
        # アップロードを使うのはメンテナンス系(9xx)の画面だけなので、同じく
        # Admin に限る。デモンストレーションモードでは誰にも許さない。
        # 以前は画面の権限判定を通らず、ログインしていなくても MEDIA_ROOT へ
        # ファイルを置けた
        if getattr(settings, 'IS_SAMPLE_MODE', False) or get_user_level(request.user) < 2:
            return JsonResponse({'form': False, 'error': 'ファイルを受け付けられません'}, status=403)

        # Dropzone (JS側) の paramName: "file" に合わせて 'file' で取得する
        files = request.FILES.getlist('file')
        
        if not files:
            files = request.FILES.getlist('file_field')

        if not files:
           return JsonResponse({'form': False, 'error': 'ファイルが受信できませんでした'}, status=400)

        for f in files:
            fileNamePath = Path(str(settings.MEDIA_ROOT) + "/" + f.name).resolve()
            
            # 親フォルダを自動作成
            fileNamePath.parent.mkdir(parents=True, exist_ok=True)

            # 🌟 拡張子による条件分岐を追加
            if fileNamePath.suffix.lower() == '.json':
                # 同期用JSONファイルは最初からUTF-8なので、変換せずそのままバイナリで保存する
                with open(fileNamePath, 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)
            else:
                # 従来のCSV等の場合は、Shift-JIS -> UTF-8 の変換ロジックを通す
                fileNamePathOriginal = Path(str(settings.MEDIA_ROOT) + "/" + f.name + ".org").resolve()
                
                with open(fileNamePathOriginal, 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)

                try:
                    with codecs.open(fileNamePathOriginal, 'r', 'shift_jis') as file:
                        content = file.read()
                except UnicodeDecodeError:
                    with codecs.open(fileNamePathOriginal, 'r', 'utf-8') as file:
                        content = file.read()
            
                with codecs.open(fileNamePath, 'w', 'utf-8') as file:
                    file.write(content)

        return JsonResponse({'form': True})

# ▼ ユーザーの権限レベルを数値化するヘルパー関数
def get_user_level(user):
    if not user.is_authenticated:
        # ログインなしのモードでは、未ログインを指定の権限として扱う
        anonymous = sub_anonymous_level()
        if anonymous is not None:
            return anonymous
        return -1 # 未ログインユーザーは強制的に -1 (権限なし)
    if user.is_superuser:
        return 2  # Admin
    if user.groups.filter(name='Manager').exists():
        return 1  # Manager
    return 0      # Staff (一般・アルバイト等含むデフォルト)

# ▼ 動的アクセス権限判定ロジック
def has_permission(user, template_name):
    # ----------------------------------------------------
    # 1. サンプルモードの特別判定
    # ----------------------------------------------------
    if getattr(settings, 'IS_SAMPLE_MODE', False):
        # メンテナンス系（ファイル名が9で始まる画面）は強制ブロック
        if template_name.startswith('9'):
            return False
        # それ以外の画面はサンプルモードなら全て許可
        return True

    # ----------------------------------------------------
    # 2. 変更を許さない画面（権限設定画面など）
    # ----------------------------------------------------
    # DBの値によらず固定する。設定を誤って権限設定画面を開けなくなると
    # DBを直接編集しない限り復旧できなくなるため。
    if template_name in Config.FIXED_PERMISSION_LEVELS:
        fixed_level = Config.FIXED_PERMISSION_LEVELS[template_name]
        # -1 (非表示) は通常判定と同じく Admin であってもブロックする。
        # 比較だけで判定すると get_user_level() の最小値が -1 のため、
        # 未ログインを含む全員が通ってしまう。
        if fixed_level == -1:
            return False
        return get_user_level(user) >= fixed_level

    # ----------------------------------------------------
    # 3. 通常モード（DB判定）
    # ----------------------------------------------------
    # DBに定義が無い画面は config の既定値に従う。画面を追加するたびに
    # DBを更新しなくても妥当な権限で動くようにするための規定。
    default_level = Config.get_default_permission_level(template_name)

    try:
        perm = Tz910Permission.objects.filter(template_name=template_name).first()
        if not perm:
            required_level = default_level
        else:
            required_level = perm.required_level
    except Exception:
        # DB接続エラー等の場合も既定に倒す
        required_level = default_level

    # ----------------------------------------------------
    # 4. 権限レベルの比較
    # ----------------------------------------------------
    # -1 (非表示) はAdminであっても強制ブロック
    if required_level == -1:
        return False

    # ユーザーレベルが要求レベル以上なら許可
    user_level = get_user_level(user)
    return user_level >= required_level

