# GF Dashboard

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## 概要
来場者数(朝・昼・夜、メンバー/ビジター、スクール、当日の天気)と売上データを統合的に表示することができる、データ表示に特化したゴルフ練習場向けのWebダッシュボードシステムです。  
（元データについては、個々のシステムからGF Dashboardのデータベースへ逐次登録してもらう形となります）

## DEMO
以下のURLにデモンストレーションシステムを用意しています。
👉[https://gfdash-demo.green-fld.jp/](https://gfdash-demo.green-fld.jp/)

## Features (特徴)
- **アクセス制御:** ユーザー属性（権限レベル）により、「来場者のみ閲覧」「来場者と売上の両方を閲覧」といった柔軟な表示制御が可能です。
- **データ視覚化:** 来場者数や売上をグラフ表示し、月の着地見込みを直感的に把握できます。前年比のパーセンテージや過去の同月比較も容易です。
- **天候データとの相関分析:** 来場者数と天候情報（温度・風速）を同一グラフ上に表示し、客足が天候にどう影響されたかを分析できます。
- **気象庁APIの自動連携:** アメダスデータを利用。手動インポートのほか、cron設定により最寄りの観測所データを自動取得・同期します。

## Requirements (必須環境)
- Python 3.13
- PostgreSQL 18
- Django 6.0
- Docker / Docker Compose (推奨)
*(※その他のPython依存ライブラリについては `requirements.txt` を参照)*

## Database Specifications
本システムの詳細なデータベース仕様（ER図、テーブル定義、各種マスタコード）については、以下のドキュメントを参照してください。

👉 **[GFdash データベース総合仕様書 (docs/db_schema_index.md)](./docs/db_schema_index.md)**  
👉 **[GFdash コード・定数定義書](./codes.md)**

## Installation

### Dockerを利用する場合（推奨）
付属の `docker-compose.yml` を使用することで、自動的に実行環境を構築できます。

1. 環境変数の設定
   `.env.example` をコピーして `.env` を作成し、環境に合わせて修正してください。
2. テストユーザーの作成（任意）
   ユーザー制御をテストしたい場合は、`dev_params.example.json` を `dev_params.json` にリネームし、パスワードを設定してください。
3. コンテナの起動
```bash
   docker-compose up -d
```

### 手動で構築する場合
PostgreSQLのテーブル定義SQLを以下の順序で実行してください。
```bash
00_*.sql -> 01_*.sql -> 02_*.sql
```

## Commands(運用コマンド)
Djangoの管理コマンドを利用して、天候情報の自動取得を行います。

### 前日分の天候情報を取得
```bash
python manage.py get_daily_weather
```

Note: cronに組み込むことで、自動で天候情報を取得します。実行タイミングにより、天気情報のデータが無く取得出来ない場合があります。その場合は再実行することで取得可能です（確実に取得するため、12時以降の実行を推奨します）。

### 日付を指定して天候情報を取得
```bash
python manage.py get_daily_weather --date yyyy-mm-dd
```

## Other libraries
**Gentelella (Modern Bootstrap Admin Dashboard Template)**
- [https://github.com/colorlibhq/gentelella](https://github.com/colorlibhq/gentelella)
- [https://github.com/GiriB/django-gentelella](https://github.com/GiriB/django-gentelella)  
※ Django 6.0で動作するようにDjango版に独自のカスタマイズを加えています。

## Author
* 中野亮太
* グリーンフィールド株式会社
* dev@green-fld.jp

## License
"GF Dashbord" is under [MIT license](https://en.wikipedia.org/wiki/MIT_License).
