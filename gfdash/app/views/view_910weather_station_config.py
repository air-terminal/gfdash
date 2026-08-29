from django.db import transaction
from django.db.models import Count, Q
from django.http import QueryDict

from datetime import date, timedelta

import json
import re
import requests

from bs4 import BeautifulSoup

from ..models import Tz103WeatherStation
from ..utils.com_utils import com_get_weather_station_config
from ..utils.com_utils import com_save_weather_station_config

# 接続テストで叩く気象庁の日別データページ
#   気象官署は daily_s1.php、アメダスは daily_a1.php と参照先が分かれている
JMA_DAILY_URL = {
    's': 'https://www.data.jma.go.jp/stats/etrn/view/daily_s1.php',
    'a': 'https://www.data.jma.go.jp/stats/etrn/view/daily_a1.php',
}

JMA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


# 気象庁は南極（昭和基地）を都府県・地方コード 99 として扱っているが、
# 練習場の所在地にはなり得ないため選択肢から除く。
# 気温・風速の欄には気象官署も並ぶようになり「官署とアメダスが両方ある」と
# いう条件では除外できなくなったため、コードを明示して除いている。
EXCLUDED_PREC_NO = ('99',)


def sub910_selectable_stations():
    """
    設定に使える観測地点だけを絞り込んだクエリセットを返す。

    - 観測終了済みの地点は除外する。廃止地点が同名の現役地点と並ぶため
      （例: 新島・神津島）、画面上で区別できず誤選択の原因になる。
    - 気温・風速・降水量が揃わない地点は除外する。アメダスの約1/4は
      降水量しか観測しておらず、選ぶと気温・風速が永久にNULLになる。
      気象官署は全項目を観測しているため、この条件で除外されない。
    """
    return Tz103WeatherStation.objects.filter(
        end_date__isnull=True,
        has_temp=True,
        has_wind=True,
        has_rainfall=True,
    ).exclude(prec_no__in=EXCLUDED_PREC_NO)


def get910_main(ctx):
    # 選択可能な気象官署がある都府県のみを選択肢にする。天気概況は気象官署から
    # しか取得できないため、官署が無い都府県は設定を完成させられない。
    # 気温・風速の欄には官署も並ぶので、官署が1件でもあれば両方の欄が埋まる。
    prefectures = (
        sub910_selectable_stations()
        .values('prec_no', 'prec_name')
        .annotate(kansyo=Count('id', filter=Q(station_type='s')))
        .filter(kansyo__gt=0)
        .order_by('prec_no')
    )

    ctx['prefectures'] = list(prefectures)
    ctx['station_config'] = com_get_weather_station_config()

    return ctx


def post910_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    tmpParam = dic.get('getMode')

    if tmpParam == 'stations':
        ret = sub910_get_stations(dic.get('precNo'))
    elif tmpParam == 'save':
        ret = sub910_save(dic.get('precNo'), dic.get('blockNoKansyo'), dic.get('blockNoAmedas'))
    else:
        ret = {'save_success': False, 'err_message': '不正なリクエストです。'}

    return json.dumps(ret, ensure_ascii=False)


def sub910_get_stations(pPrecNo):
    """指定された都府県の観測地点を、気象官署／アメダスの各欄向けに返す"""
    if not pPrecNo:
        return {'kansyo': [], 'amedas': []}

    stations = (
        sub910_selectable_stations()
        .filter(prec_no=pPrecNo)
        .values('block_no', 'station_name', 'station_type')
        .order_by('station_type', 'station_name')
    )

    ret = {'kansyo': [], 'amedas': []}
    for s in stations:
        item = {
            'block_no': s['block_no'],
            'station_name': s['station_name'],
            'station_type': s['station_type'],
        }
        if s['station_type'] == 's':
            ret['kansyo'].append(item)
        # 気象官署はアメダスと同じ項目をすべて観測しているため、
        # 市街地の官署が最寄りというケースに備えてアメダス欄にも並べる。
        ret['amedas'].append(item)

    return ret


def sub910_save(pPrecNo, pBlockNoKansyo, pBlockNoAmedas):
    """接続テストに成功した場合のみ tz901 へ保存する"""
    if not pPrecNo or not pBlockNoKansyo or not pBlockNoAmedas:
        return {'save_success': False, 'err_message': '都府県・気象官署・アメダスをすべて選択してください。'}

    try:
        # 天気概況は気象官署からしか取得できないため、官署欄は種別を固定する。
        kansyo = sub910_selectable_stations().get(
            prec_no=pPrecNo, block_no=pBlockNoKansyo, station_type='s'
        )
        # アメダス欄は官署も選べるので種別を絞らない。
        amedas = sub910_selectable_stations().get(
            prec_no=pPrecNo, block_no=pBlockNoAmedas
        )
    except Tz103WeatherStation.DoesNotExist:
        return {'save_success': False, 'err_message': '選択された観測地点がマスタに存在しないか、設定に使用できません。'}

    # 保存前に、実際に気象庁からデータを取得できるかを確認する。
    # ここで弾いておかないと、翌日以降のバッチが無言で失敗し続けることになる。
    # 官署とアメダスに同じ地点を選べるので、その場合は1回だけ確認する。
    test_results = []
    targets = [('気象官署', kansyo)]
    if amedas.pk != kansyo.pk:
        targets.append(('アメダス', amedas))

    for label, station in targets:
        ok, message = sub910_test_connection(station)
        test_results.append({'label': label, 'station_name': station.station_name, 'ok': ok, 'message': message})

    if not all(r['ok'] for r in test_results):
        ng = [f"{r['label']}（{r['station_name']}）: {r['message']}" for r in test_results if not r['ok']]
        return {
            'save_success': False,
            'test_results': test_results,
            'err_message': '気象庁からデータを取得できなかったため保存を中止しました。<br>' + '<br>'.join(ng),
        }

    with transaction.atomic():
        com_save_weather_station_config(kansyo, amedas)

    return {
        'save_success': True,
        'test_results': test_results,
        'err_message': f'気象官署「{kansyo.station_name}」／アメダス「{amedas.station_name}」を設定しました。',
    }


def sub910_test_connection(pStation):
    """指定した観測地点の日別ページを取得し、実際に観測値が入っているかを確認する"""
    url = JMA_DAILY_URL.get(pStation.station_type)
    if not url:
        return False, '地点種別が不正です。'

    # 当月は先の日付が未観測で埋まっていないため、前月のデータで確認する。
    # 年月を空にすると気象庁は表を含まない案内ページを返すので必ず指定する。
    today = date.today()
    target = date(today.year, today.month, 1) - timedelta(days=1)

    params = {
        'prec_no': pStation.prec_no,
        'block_no': pStation.block_no,
        'year': str(target.year),
        'month': str(target.month),
        'day': '',
        'view': 'p1',
    }

    try:
        res = requests.get(url, params=params, headers=JMA_HEADERS, timeout=15)
    except requests.RequestException as e:
        return False, f'気象庁サイトへ接続できませんでした（{type(e).__name__}）。'

    if res.status_code != 200:
        return False, f'気象庁サイトが HTTP {res.status_code} を返しました。'

    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, 'lxml')

    # データページの表にはidが付いていないため、行数が最も多い表を本体とみなす。
    # 取得処理(get_daily_weather)も同じ方法で表を特定している。
    tables = soup.find_all('table')
    if not tables:
        return False, '日別データの表が見つかりませんでした。地点コードを確認してください。'

    table = max(tables, key=lambda t: len(t.find_all('tr')))
    if len(table.find_all('tr')) < 20:
        return False, '日別データの表が取得できませんでした。地点コードを確認してください。'

    # 観測していない項目や廃止地点の値は「///」で埋められる。観測値は必ず
    # 小数を含むため、小数が1つも無ければデータが提供されていないと判断する。
    if not re.search(r'\d+\.\d', table.get_text()):
        return False, f'{target.year}年{target.month}月の観測データがありませんでした。別の地点を選択してください。'

    return True, f'{target.year}年{target.month}月のデータを取得できました。'
