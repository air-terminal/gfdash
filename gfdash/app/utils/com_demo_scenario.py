"""
デモデータのシナリオ（demo_data/scenario.json）と、デモ用の第2休日カレンダーの共通処理。

デモの来場者データ（gen_revised_csv）・第2休日カレンダー（gen_demo_calendar）・
月次所見（gen_demo_remarks）を、同じ出来事の一覧から作る。所見は「出来事の効果」を
予測に入れる機能なので、効果の入っていないデータに所見だけを足すと、補正が予測を
悪くするデモになる。データと所見の出どころを1つにして、食い違いを作らない。
"""

import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import holidays
from django.conf import settings

# manage.py の1つ上（リポジトリの直下）にある demo_data
DEMO_DATA_DIR = Path(settings.BASE_DIR).parent / 'demo_data'
DEFAULT_SCENARIO_PATH = DEMO_DATA_DIR / 'scenario.json'
DEFAULT_HOLIDAY2_PATH = DEMO_DATA_DIR / 'calendar' / 'holiday2_demo.csv'

EVENT_TYPE_PERIOD = 'period'
EVENT_TYPE_LEVEL_SHIFT = 'level_shift'
EVENT_TYPE_CLOSURE = 'closure'

# デモ用の第2休日カレンダーの種別（tz901 code:008 の枝番）
DEMO_HOLIDAY2_CLS = 1
HOLIDAY2_HOLIDAY = 1
HOLIDAY2_WORKDAY = 2

# 祝日だが近隣の事業所は稼働する、という扱いにする祝日。
# 2019年までは「体育の日」、2020年から「スポーツの日」
HOLIDAY2_WORKING_HOLIDAYS = ('海の日', 'スポーツの日', '体育の日')

DATE_FORMAT = '%Y-%m-%d'


def com_parse_date(pValue):
    return datetime.strptime(pValue, DATE_FORMAT).date()


def com_load_scenario(pPath=None):
    """シナリオを読む。日付は date にして返す"""
    path = Path(pPath) if pPath else DEFAULT_SCENARIO_PATH
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    for event in data.get('events', []):
        event['_start'] = com_parse_date(event['start_date'])
        event['_end'] = com_parse_date(event['end_date']) if event.get('end_date') else None

    # 出来事の無い日の備考。シナリオと同じフォルダの daily_memos.json に置く
    # （LLM で一度だけ作って固定したもの。無ければ備考なし）
    memos_path = path.parent / 'daily_memos.json'
    if memos_path.exists():
        with open(memos_path, encoding='utf-8') as f:
            data['daily_memos'] = json.load(f).get('memos') or {}
    return data


def com_event_active(pEvent, pDay):
    """その日に出来事が効いているか。恒久的な変化は開始日以降ずっと効く"""
    if pDay < pEvent['_start']:
        return False
    return pEvent['_end'] is None or pDay <= pEvent['_end']


def com_day_effect(pScenario, pDay):
    """
    その日の (倍率, 臨時休業か, 日次備考のリスト) を返す。

    同じ日に複数の出来事が効いていれば倍率を掛け合わせる。予測の補正
    （所見の係数）も重なった係数を掛け合わせるので、それと同じ扱いにする。
    """
    factor = 1.0
    closed = False
    memos = []
    key = pDay.strftime(DATE_FORMAT)

    for event in pScenario.get('events', []):
        memo = (event.get('memos') or {}).get(key)
        if memo:
            memos.append(memo)
        if not com_event_active(event, pDay):
            continue
        if event['type'] == EVENT_TYPE_CLOSURE:
            closed = True
        elif event.get('true_factor') is not None:
            factor *= float(event['true_factor'])

    # 出来事の無い日の備考（雨で客足が鈍い等）。天候と来場者数から一度だけ
    # 作ってシナリオに固定してある。データの効果は持たない（天候の効果は別に掛かる）
    daily = (pScenario.get('daily_memos') or {}).get(key)
    if daily:
        memos.append(daily)

    return factor, closed, memos


def com_read_demo_weather(pDir=None):
    """
    同梱の天候データ（気象庁の日別値 CSV。demo_data/weather/*日別*.csv）を読み、
    {date: {'max_temp', 'precip', 'summary'}} で返す。precip は「1時間降水量の日最大」
    （README の取得項目。降水量の合計は取得していない）、summary は昼の天気概況。

    デモの来場者数に天候の効果を入れるために使う。天候と無関係に作ると、
    雨の日の日次備考とデータが食い違い、予測も天候の効果を学べない。
    """
    folder = Path(pDir) if pDir else DEMO_DATA_DIR / 'weather'
    weather = {}
    for path in sorted(folder.glob('*日別*.csv')):
        with open(path, encoding='cp932') as f:
            rows = list(csv.reader(f))
        # 列は位置ではなく見出しの名前で探す。ダウンロードのときに選んだ項目で
        # 列の並びが変わる（README の項目どおりなら同じ並びになる）
        header = next((r for r in rows if r and r[0] == '年月日'), None)
        if header is None:
            continue
        col_temp = sub_col(header, '最高気温')
        col_rain = sub_col(header, '1時間降水量の最大')
        col_summary = sub_col(header, '天気概況(昼')

        for row in rows:
            # データ行は先頭が年月日（2026/3/11）
            if not row or not row[0][:1].isdigit():
                continue
            try:
                day = datetime.strptime(row[0], '%Y/%m/%d').date()
            except ValueError:
                continue
            weather[day] = {
                'max_temp': sub_float(row, col_temp),
                'precip': sub_float(row, col_rain) or 0.0,
                'summary': row[col_summary] if col_summary is not None and col_summary < len(row) else '',
            }
    return weather


def sub_col(pHeader, pName):
    """見出しが pName で始まる最初の列の位置。無ければ None"""
    return next((i for i, h in enumerate(pHeader) if h.startswith(pName)), None)


def sub_float(pRow, pCol):
    if pCol is None or pCol >= len(pRow) or not pRow[pCol]:
        return None
    try:
        return float(pRow[pCol])
    except ValueError:
        return None


def com_weather_factor(pScenario, pWeather):
    """
    その日の天候による倍率。雨と猛暑で減らす。効果の強さは scenario.json の
    weather_effect に持つ。天候データの無い日は 1.0
    """
    if not pWeather:
        return 1.0
    effect = pScenario.get('weather_effect') or {}
    factor = 1.0
    precip = pWeather.get('precip') or 0.0
    if precip >= float(effect.get('heavy_rain_mm', 10)):
        factor *= float(effect.get('heavy_rain', 1.0))
    elif precip >= float(effect.get('rain_mm', 1)):
        factor *= float(effect.get('rain', 1.0))
    max_temp = pWeather.get('max_temp')
    if max_temp is not None and max_temp >= float(effect.get('hot_c', 33)):
        factor *= float(effect.get('hot', 1.0))
    return factor


def com_jp_holidays(pYears):
    """国民の祝日を {date: 名称} で返す。holidays は Prophet の依存として入っている"""
    return dict(holidays.JP(years=list(pYears), language='ja'))


# ------------------------------------------------------------------
# デモ用の第2休日カレンダー
#
# 祝日だけでは、正月休み（1/2〜1/3 は祝日ではない）、メーデー前後の有休取得
# 推奨日、お盆などの人の動きを表せない。架空の「近隣の大規模事業所」の休日を
# 規則から作る。データの全期間を登録しないと、未登録の期間が「第2休日では
# なかった」と学習されて精度が落ちるため、期間は学習期間より広く取る。
# ------------------------------------------------------------------

def com_build_holiday2_rows(pFromYear, pToYear):
    """
    第2休日カレンダーの行を規則から作る。import_holiday2 の CSV と同じ形
    （calendar_cls, from_day, to_day, day_cls, memo）の dict のリスト。

    範囲の中に土日が入っても構わない。予測の回帰変数は「通常の週パターンと
    食い違う日」だけを使うので、土日の休日は無視される。人が読める連休の
    かたまりで書いておくほうが、直しやすい。
    """
    rows = []
    jp = com_jp_holidays(range(pFromYear, pToYear + 1))

    for year in range(pFromYear, pToYear + 1):
        # 年末年始は前年の12/29から。初年は前年末の分も入れる
        if year == pFromYear:
            rows.append(sub_row(date(year - 1, 12, 29), date(year, 1, 3), HOLIDAY2_HOLIDAY, '年末年始休暇'))
        rows.append(sub_row(date(year, 4, 29), date(year, 5, 5), HOLIDAY2_HOLIDAY,
                            'GW連休（メーデー・有休取得推奨日を含む）'))
        rows.append(sub_row(date(year, 8, 13), date(year, 8, 16), HOLIDAY2_HOLIDAY, '夏季休暇'))
        rows.append(sub_row(date(year, 12, 29), date(year + 1, 1, 3), HOLIDAY2_HOLIDAY, '年末年始休暇'))

        for day, name in sorted(jp.items()):
            if day.year == year and name in HOLIDAY2_WORKING_HOLIDAYS:
                rows.append(sub_row(day, None, HOLIDAY2_WORKDAY, f'{name}（祝日だが稼働）'))

    return sorted(rows, key=lambda r: r['from_day'])


def sub_row(pFrom, pTo, pDayCls, pMemo):
    return {
        'calendar_cls': DEMO_HOLIDAY2_CLS,
        'from_day': pFrom,
        'to_day': pTo,
        'day_cls': pDayCls,
        'memo': pMemo,
    }


def com_write_holiday2_csv(pRows, pPath):
    path = Path(pPath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['calendar_cls', 'from_day', 'to_day', 'day_cls', 'memo'])
        for row in pRows:
            writer.writerow([
                row['calendar_cls'],
                row['from_day'].strftime(DATE_FORMAT),
                row['to_day'].strftime(DATE_FORMAT) if row['to_day'] else '',
                row['day_cls'],
                row['memo'],
            ])


def com_read_holiday2_days(pPath=None):
    """
    第2休日カレンダーの CSV を {date: day_cls} に展開する。

    データを作る側（gen_revised_csv）も、取り込む側（import_holiday2）と同じ
    CSV を読む。カレンダーとデータが食い違うと、予測は効果の入っていない日を
    休日として学習する。
    """
    path = Path(pPath) if pPath else DEFAULT_HOLIDAY2_PATH
    days = {}
    if not path.exists():
        return days

    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            start = com_parse_date(row['from_day'])
            end = com_parse_date(row['to_day']) if row.get('to_day') else start
            day_cls = int(row.get('day_cls') or HOLIDAY2_HOLIDAY)
            day = start
            while day <= end:
                days[day] = day_cls
                day += timedelta(days=1)
    return days
