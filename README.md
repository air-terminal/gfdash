# GF Dashboard

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## 概要
来場者数(朝・昼・夜、メンバー/ビジター、スクール、当日の天気)と売上データを統合的に表示することができる、データ表示に特化したゴルフ練習場向けのWebダッシュボードシステムです。  
（元データについては、個々のシステムからGF Dashboardのデータベースへ逐次登録してもらう形となります）

![Top Image](/docs/img/screen_shot.png)

[**View Live Demo**](https://gfdash-demo.green-fld.jp/)

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
   1. `.env.example` をコピーして `.env` を作成し、環境に合わせて修正してください。

      最低限、SECRET_KEY、POSTGRES_PASSWORD、DJANGO_SUPERUSER_PASSWORDを設定してください。  
      DJANGO_SUPERUSER_USERNAMEはAdmin区分のユーザー名となります。  
      また、POSTGRES_DBとPOSTGRES_USERは変更しないようお願いします。　　

   1. ユーザー・パスワードによる画面制御の設定

      「デモンストレーションモード」をオンにすることでパスワード無しで運用することができます。

      ```text
      \gfdash\setteings.py

      IS_SAMPLE_MODE = True
      ```
      ※サーバーがインターネット上にある場合、誰でも閲覧することができる状態となるため、設定には十分注意して下さい。


2. テストユーザーの作成（任意）
   ユーザー制御をテストしたい場合は、`dev_params.example.json` を `dev_params.json` にリネームし、パスワードを設定してください。  

   ここで設定しなくても、admin画面(django標準機能)よりユーザーの追加・削除ができます  

3. マスタデータの設定  
   `\containers\postgres\sql\`配下にマスタデータが定義されたsqlが格納されており、環境に応じて変更します。  
   1. 02_tz901_setup.sql  
   **天候情報取得の設定**

      | 項目名 | 設定する値 |
      | :------- | :------- |
      | 官署地点、アメダス地点 | 官署地点、アメダス地点の名称 |
      | 官署地点prec_no、アメダス地点prec_no | 天候情報を取得する場所の気象庁の都府県・地方コード |
      | 官署地点block_no、アメダス地点block_no | 天候情報を取得する場所の気象庁観測地点コード |

      **※官署地点とアメダス地点の違いについて**  
      官署地点:天候情報が取得できる地点(気象台、測候所と呼ばれている地点です。記号:◎)  
      アメダス地点:最寄りの測候地点(アメダスと呼ばれている地点です。記号:○(赤色))  

   1. 02_tz910_setup.sql  
   **画面別パーミッションの設定**  
      画面別にユーザー権限レベルを設定します。  
      設定値については、[GFdash コード・定数定義書](./codes.md)を参照してください。  

4. コンテナの起動
```bash
   docker-compose up -d
```
5. 平年値、過去の天候データの設定
   平年値、過去の天候データの設定は、通常モード

   1. 平年値の取得
      [気象庁のホームページ”過去の気象データ・ダウンロード”](https://www.data.jma.go.jp/risk/obsdl/index.php)より、気温に関する情報の平年値をダウンロードします。

      | グループ | 取得項目 |
      | :------- | :------- |
      | データの種類 | "日別値"を選択 |
      | 過去の平均値との比較オプション | "平年値も表示"にチェック |
      | 気温 | "日平均気温"、"日最高気温"、"日最低気温"にチェック |
      | 期間 | "最近１年"のボタンを押下して下さい。 |

   1. 平年値の登録  
      **※平年値を登録するには、デモンストレーションモード=OFF、Superuser権限のユーザーにて作業を行って下さい**  
      画面の「メンテナンス」「平年気温情報アップロード」画面より、平年値の取得でダウンロードしたcsvファイルを画面に登録し、"Upload"ボタンを押下して下さい。  

   1. 日別値の取得
      [気象庁のホームページ”過去の気象データ・ダウンロード”](https://www.data.jma.go.jp/risk/obsdl/index.php)より、日別の気象情報をダウンロードします。   

      | グループ | 取得項目 |
      | :------- | :------- |
      | データの種類 | "日別値"を選択 |
      | 気温 | "日平均気温"、"日最高気温"、"日最低気温"にチェック |
      | 降水 | "「1時間」降水量の日最大"にチェック |
      | 風 | "日最大風速（風向）"、"日最大瞬間風速（風向）"にチェック |
      | 雲量／天気 | "天気概況（昼：06時～18時）※1"、"天気概況（夜：18時～翌日06時）※"にチェック |
      | 期間 | データを取得したい期間を設定して下さい※2 |

      ※1 官署地点のみ設定してください。  
      ※2 選択済みのデータ量が100%を超える場合は、期間を分割してダウンロードして下さい。  

   1. 時別値の取得
      [気象庁のホームページ”過去の気象データ・ダウンロード”](https://www.data.jma.go.jp/risk/obsdl/index.php)より、日別の気象情報をダウンロードします。   

      | グループ | 取得項目 |
      | :------- | :------- |
      | データの種類 | "時別値"を選択 |
      | 項目 | "気温"、"降水量（前1時間）"、"風向・風速"、"天気 ※"にチェック |
      | 期間 | データを取得したい期間を設定して下さい※2 |

      ※1 官署地点のみ設定してください。  
      ※2 選択済みのデータ量が100%を超える場合は、期間を分割してダウンロードして下さい。  

   1. 日別値、時別値データの登録  
      **※日別値、時別値を登録するには、デモンストレーションモード=OFF、Superuser権限のユーザーにて作業を行って下さい**  
      画面の「メンテナンス」「天候情報アップロード」画面より、日別値、時別値の取得でダウンロードしたcsvファイルを画面に登録し、"Upload"ボタンを押下して下さい。csvファイルは複数同時登録することができます。  


### 手動で構築する場合
マスタデータの設定の上、PostgreSQLのテーブル定義SQLを以下の順序で実行してください。
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
Note: 天候情報取得コマンドでは、気象庁のページより天候情報をスクレイピングして情報を取得しています。
初期データをセットアップする等大量のデータを取得する場合、気象庁のサーバーに負荷がかかる為 **5. 平年値、過去の天候データの設定** の方法を使用して下さい。

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
