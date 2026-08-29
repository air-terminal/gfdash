from django.core.management.base import BaseCommand, CommandError
from datetime import date, datetime
from pathlib import Path
import re
import time
import requests

from bs4 import BeautifulSoup

JMA_SELECT_BASE = 'https://www.data.jma.go.jp/stats/etrn/select'
JMA_PREF_INDEX = JMA_SELECT_BASE + '/prefecture00.php'
JMA_PREF_PAGE = JMA_SELECT_BASE + '/prefecture.php?prec_no={prec_no}&block_no=&year=&month=&day=&view='

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# 都府県・地方の一覧ページのリンク
#   <area alt="東京都" href="prefecture.php?prec_no=44&block_no=&...">
PREC_HREF_RE = re.compile(r'prefecture\.php\?prec_no=(\d+)')

# 地点一覧ページに埋め込まれた地点情報。ページ内の関数定義は次の並びになっている。
#   viewPoint(as, bk_no, ch, ch_kn, lat_d, lat_m, lon_d, lon_m, height,
#             f_pre, f_wsp, f_tem, f_sun, f_snc, f_hum, ed_y, ed_m, ed_d, bikou1..5)
#
# 観測項目(f_pre:降水量 / f_wsp:風速 / f_tem:気温)と観測終了日(ed_y/ed_m/ed_d)を
# 取り込む。アメダスには降水量しか観測しない地点や既に廃止された地点が多く、
# それらを設定画面の選択肢から除くために必要。ed_y が 9999 なら現役。
VIEWPOINT_RE = re.compile(
    r"viewPoint\("
    r"'([as])',"        # 1  as       種別
    r"'(\d+)',"         # 2  bk_no    block_no
    r"'([^']*)',"       # 3  ch       地点名
    r"'[^']*',"         # 4  ch_kn    カナ
    r"'[^']*','[^']*'," # 5,6 lat     緯度
    r"'[^']*','[^']*'," # 7,8 lon     経度
    r"'[^']*',"         # 9  height   標高
    r"'([^']*)',"       # 10 f_pre    降水量
    r"'([^']*)',"       # 11 f_wsp    風速
    r"'([^']*)',"       # 12 f_tem    気温
    r"'[^']*',"         # 13 f_sun    日照
    r"'[^']*',"         # 14 f_snc    積雪
    r"'[^']*',"         # 15 f_hum    湿度
    r"'([^']*)',"       # 16 ed_y     観測終了年
    r"'([^']*)',"       # 17 ed_m     観測終了月
    r"'([^']*)'"        # 18 ed_d     観測終了日
)


class Command(BaseCommand):
    help = (
        '気象庁サイトから全国の観測地点一覧を取得し、'
        'tz103_weather_station の初期データSQLを生成します。'
        '生成済みSQLはリポジトリに同梱しているため、通常の運用では実行不要です。'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--out',
            type=str,
            default='containers/postgres/sql/02_tz103_setup.sql',
            help='出力するSQLファイルのパス（既定: containers/postgres/sql/02_tz103_setup.sql）',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=1.0,
            help='気象庁サイトへのアクセス間隔（秒）。既定: 1.0',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help='HTTPタイムアウト（秒）。既定: 15',
        )

    def handle(self, *args, **options):
        out_path = Path(options['out'])
        interval = options['sleep']
        timeout = options['timeout']

        self.stdout.write('--- 気象観測地点マスタの生成を開始します ---')

        prefectures = self._fetch_prefectures(timeout)
        if not prefectures:
            raise CommandError('都府県・地方の一覧を取得できませんでした。')
        self.stdout.write(f'都府県・地方: {len(prefectures)}件')

        rows = []
        for i, (prec_no, prec_name) in enumerate(prefectures, start=1):
            stations = self._fetch_stations(prec_no, timeout)
            for station in stations:
                station['prec_no'] = prec_no
                station['prec_name'] = prec_name
                rows.append(station)

            self.stdout.write(f'  [{i}/{len(prefectures)}] {prec_name} (prec_no={prec_no}): {len(stations)}地点')

            # 気象庁サイトへ連続アクセスしないよう間隔を空ける
            if i < len(prefectures):
                time.sleep(interval)

        if not rows:
            raise CommandError('観測地点を1件も取得できませんでした。ページ構造が変わった可能性があります。')

        self._write_sql(out_path, rows)

        kansyo = sum(1 for r in rows if r['station_type'] == 's')
        amedas = sum(1 for r in rows if r['station_type'] == 'a')
        # 設定画面で実際に選べる地点数。現役かつ気温・風速・降水量が揃うもの。
        usable = sum(
            1 for r in rows
            if r['end_date'] is None and r['has_temp'] and r['has_wind'] and r['has_rainfall']
        )
        self.stdout.write(self.style.SUCCESS(
            f'{out_path} を生成しました'
            f'（合計 {len(rows)}件 / 気象官署 {kansyo}件・アメダス {amedas}件'
            f' / うち設定画面で選択可能 {usable}件）'
        ))

    def _fetch_prefectures(self, timeout):
        """都府県・地方の一覧を (prec_no, prec_name) のリストで返す"""
        res = requests.get(JMA_PREF_INDEX, headers=HEADERS, timeout=timeout)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'lxml')

        result = []
        seen = set()
        for area in soup.find_all('area'):
            href = area.get('href') or ''
            name = (area.get('alt') or '').strip()
            m = PREC_HREF_RE.search(href)
            if not m or not name:
                continue
            prec_no = m.group(1)
            if prec_no in seen:
                continue
            seen.add(prec_no)
            result.append((prec_no, name))

        return sorted(result, key=lambda x: int(x[0]))

    def _fetch_stations(self, prec_no, timeout):
        """指定した都府県の観測地点を dict のリストで返す"""
        url = JMA_PREF_PAGE.format(prec_no=prec_no)
        res = requests.get(url, headers=HEADERS, timeout=timeout)
        res.encoding = res.apparent_encoding

        result = []
        seen = set()
        for m in VIEWPOINT_RE.finditer(res.text):
            station_type, block_no, station_name = m.group(1), m.group(2), m.group(3).strip()
            if not station_name:
                continue
            # 同じ地点が onmouseover と onclick で二重に出現するため除外する
            key = (station_type, block_no)
            if key in seen:
                continue
            seen.add(key)

            result.append({
                'station_type': station_type,
                'block_no': block_no,
                'station_name': station_name,
                # フラグは 0 以外を「観測あり」とする（日照などは 2 が使われている）
                'has_rainfall': m.group(4) not in ('', '0'),
                'has_wind': m.group(5) not in ('', '0'),
                'has_temp': m.group(6) not in ('', '0'),
                'end_date': self._parse_end_date(m.group(7), m.group(8), m.group(9)),
            })

        return sorted(result, key=lambda x: (x['station_type'], x['block_no']))

    @staticmethod
    def _parse_end_date(pYear, pMonth, pDay):
        """観測終了日を date で返す。現役（9999/99/99）なら None"""
        if pYear == '9999' or not pYear:
            return None
        try:
            return date(int(pYear), int(pMonth), int(pDay))
        except (TypeError, ValueError):
            # 年だけ分かっていて月日が不正な場合も「終了済み」として扱いたいので
            # 元日に丸めて返す。判定に使うのは日付の有無だけ。
            try:
                return date(int(pYear), 1, 1)
            except (TypeError, ValueError):
                return None

    def _write_sql(self, out_path, rows):
        generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = [
            '-- 気象観測地点マスタ (tz103_weather_station) 初期データ',
            '--',
            '-- 出典: 気象庁「過去の気象データ検索」 https://www.data.jma.go.jp/stats/etrn/',
            '-- 生成: python3 gfdash/manage.py gen_weather_station_master',
            f'-- 生成日時: {generated_at}',
            '--',
            '-- ※本ファイルは自動生成です。直接編集せず、上記コマンドで再生成してください。',
            '',
            'TRUNCATE TABLE gf.tz103_weather_station;',
            '',
            'INSERT INTO gf.tz103_weather_station'
            ' (prec_no, block_no, station_type, prec_name, station_name,'
            ' has_rainfall, has_wind, has_temp, end_date) VALUES',
        ]

        values = []
        for r in rows:
            end_date = "'{}'".format(r['end_date'].isoformat()) if r['end_date'] else 'NULL'
            values.append(
                " ('{}', '{}', '{}', '{}', '{}', {}, {}, {}, {})".format(
                    self._escape(r['prec_no']),
                    self._escape(r['block_no']),
                    self._escape(r['station_type']),
                    self._escape(r['prec_name']),
                    self._escape(r['station_name']),
                    'true' if r['has_rainfall'] else 'false',
                    'true' if r['has_wind'] else 'false',
                    'true' if r['has_temp'] else 'false',
                    end_date,
                )
            )

        lines.append('\n,'.join(values) + ';')
        lines.append('')

        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Dockerコンテナ内で実行されるため改行コードはLFで固定する
        out_path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')

    @staticmethod
    def _escape(value):
        return str(value).replace("'", "''")
