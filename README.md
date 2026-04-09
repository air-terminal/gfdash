# GF Dashboard

## 概要
来場者数(朝・昼・夜、メンバー/ビジター、スクール、当日の天気)と売上データを統合的に表示することができる、データ表示に特化したゴルフ練習場向けのWebダッシュボードシステムです。
（元データについては、個々のシステムからGF Dashboardのデータベースへ逐次登録してもらう形となります）

## DEMO
以下のURLにデモンストレーションシステムを用意しています。
[https://gfdash-demo.green-fld.jp/](https://gfdash-demo.green-fld.jp/)

## Features
- ユーザー属性により、来場者のみ閲覧／来場者と売上閲覧のアクセス制御が可能です。
- 来場者数や売上をグラフ表示でき、月にどれくらい見込めるのかを視覚化します。
- 月の来場者数や売上を過去の同月と比較・確認することができます。
- 来場者数と天候情報(温度・風速)を同時表示し、来場者数が天候により左右されたのかを分析できます。
- 天気情報はアメダスのデータを利用します。手動でのCSVデータインポートの他、cron設定により最寄りの観測所のデータを自動取得できます。
- 前年比のパーセンテージをグラフ表示できます。

## Requirements
- python 3.13
- PostgreSQL 18
- asgiref 3.9.1
- Django 6.0
- sqlparse 0.5.0
- typing_extensions 4.7.1
- psycopg2 / psycopg2-binary
- django-bootstrap5
- python-dateutil
- pandas
- requests
- lxml / html5lib / beautifulsoup4
- whitenoise

## Other libraries
**Gentelella (Modern Bootstrap Admin Dashboard Template)**
- [https://github.com/colorlibhq/gentelella](https://github.com/colorlibhq/gentelella)
- [https://github.com/GiriB/django-gentelella](https://github.com/GiriB/django-gentelella)
※ Django 6.0で動作するようにDjango版に独自のカスタマイズを加えています。

## Installation
- Dockerを利用する場合は、付属の `docker-compose.yml` を使用することで、自動的に実行環境を構築できます。
.env.exampleをご利用の環境に合わせて修正して、.envとして配置して下さい。
- ユーザー制御を行う為にテストユーザーを作りたい場合は、`dev_params.example.json`をdev_params.json にリネームしてパスワードを入力した上、`docker-compose.yml`を実行して下さい。

- 手動で構築する場合、テーブル定義SQLは `00_*.sql` -> `01_*.sql` -> `02_*.sql` の順に実行してください。

## Commands
**コマンドによる天候情報の取得（実行時前日分のデータを取得します）**
python manage.py get_daily_weather

Note: cronに組み込むことで、自動で天候情報を取得します。実行タイミングにより、天気情報のデータが無く取得出来ない場合があります。その場合は再実行することで取得可能です（確実に取得するため、12時以降の実行を推奨します）。

**天候情報の取得（日付指定）**
python manage.py get_daily_weather --date yyyy-mm-dd

## Database Specifications
データベース仕様は、公開準備中です。

## Author
* 中野亮太
* グリーンフィールド株式会社
* dev@green-fld.jp

## License
"GF Dashbord" is under [MIT license](https://en.wikipedia.org/wiki/MIT_License).
