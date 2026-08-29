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
- **AI機能（ベータ）:** 過去の来場者数・気温の傾向より来場者数を予測する機能、及びローカルLLM(AI)より当月の振り返り、翌月の予測レポートを作成します。

## Requirements (必須環境)
- Python 3.13
- PostgreSQL 18
- Django 6.0
- Docker / Docker Compose (推奨)
- prophet(AI予測機能実行時)
- Ollama(AIレポート作成機能実行時、VRAM8GB以上搭載のGPUでの動作推奨)
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

### 開発時に自動リロードを使う

既定の `command` は gunicorn です。Django の開発サーバ (`runserver`) は
公式に本番利用が非推奨とされているためです。

コードを編集しながら開発する場合は、リポジトリ直下に `docker-compose.override.yml`
を作成して `command` を差し替えてください。このファイルは `.gitignore` 済みで、
`docker-compose` が自動的に読み込みます。

```yaml
services:
  web:
    command: python3 gfdash/manage.py runserver 0.0.0.0:8080
```

ワーカー数は環境変数 `GUNICORN_WORKERS` で変更できます (既定 2)。
メモリの少ない環境では 1 に、CPU に余裕がある環境では増やしてください。

```bash
# .env
GUNICORN_WORKERS=4
```

### 手動で構築する場合
マスタデータの設定の上、PostgreSQLのテーブル定義SQLを以下の順序で実行してください。
```bash
00_*.sql -> 01_*.sql -> 02_*.sql
```

## デモ環境の構築 (Quick Start)

本システムをすぐに試せるよう、AI予測やダッシュボードの表示確認に使えるデモデータと生成ツールを同梱しています。環境構築（コンテナの起動など）が完了した後、以下の手順でデモデータを投入してください。

**1. Djangoプロジェクトのディレクトリに移動**  
以降のコマンドライン作業は `manage.py` のある `gfdash` ディレクトリ内で行います。
```bash
cd gfdash
```

**2. デモ用パラメータの投入**  
初期設定やデモ用のパラメータが記載されたSQL (`02_tz901_setup_for_Demo.sql`) をデータベースに流し込みます。
環境に合わせてSQLを実行してください。同梱の docker compose 環境の場合、
web コンテナ経由で流し込めます（web イメージに postgresql-client が含まれています）。

```bash
docker compose exec web sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -f /code/demo_data/sql/02_tz901_setup_for_Demo.sql'
```

Docker を使わない場合:

```bash
psql -U ユーザー名 -d データベース名 -f ../demo_data/sql/02_tz901_setup_for_Demo.sql
```

**3. ダミー来場者データの生成**  
同梱のスクリプトを使用して、数年分のリアルな来場者ダミーデータ（CSV）をカレントディレクトリに生成します。
```bash
python manage.py gen_revised_csv
```

**4. 生成した来場者・売上データのインポート**  
生成されたダミーデータをシステム（データベース）に一括インポートします。
`import_sim_data` は「取り込み先テーブル」と「CSVファイル」の2つを引数に取ります。
手順3で生成された4つのCSVを、それぞれ対応するテーブルへ取り込んでください。

```bash
python manage.py import_sim_data ta215 revised_ta215.csv
python manage.py import_sim_data tb120 revised_tb120.csv
python manage.py import_sim_data tz201 revised_tz201.csv
python manage.py import_sim_data ta220 revised_ta220.csv
```

docker compose 環境の場合は、`manage.py` のあるディレクトリを指定して実行します
（手順3も同様です）。

```bash
docker compose exec -w /code/gfdash web python3 manage.py gen_revised_csv
docker compose exec -w /code/gfdash web python3 manage.py import_sim_data ta215 revised_ta215.csv
docker compose exec -w /code/gfdash web python3 manage.py import_sim_data tb120 revised_tb120.csv
docker compose exec -w /code/gfdash web python3 manage.py import_sim_data tz201 revised_tz201.csv
docker compose exec -w /code/gfdash web python3 manage.py import_sim_data ta220 revised_ta220.csv
```

**5. 天候データのアップロード（画面操作）**  
天候データはバッチ処理でのインポートではなく、標準機能のアップロード画面から登録します。システムにログイン後、同梱されている以下のCSVファイル（`demo_data/weather/` 内にあります）をそれぞれアップロードしてください。

*   **「平年気温情報アップロード」画面へ登録:**
    *   `横浜気温平均値.csv`
*   **「天候情報アップロード」画面へ登録（複数同時アップロード可能）:**
    *   `横浜日別.csv`, `横浜日別２.csv`
    *   `横浜時間別１.csv` 〜 `横浜時間別８.csv`

**6. AIレポート（Ollama）のセットアップ**  
ローカルLLMを用いたAIレポート機能を使用するには、以下の設定が必要です。

1. **Ollamaの起動とモデルの準備**  
   ローカルにOllamaをインストール・起動し、あらかじめ対象のLLMモデルをPull（ダウンロード）しておきます。
   ```bash
   ollama pull gemma4:e4b
   ```
   *(※別のモデル、例えば `qwen2.5:7b` などを使用する場合は、そちらをPullしてください)*

2. **設定ファイル（gfdash/settings.py または .env）の変更**  
   環境に合わせて、以下の項目を調整します。
   * **`DISABLE_BATCH_EXECUTION`**: AIバッチ処理（予測やLLMレポート生成など）の無効化フラグです。初期値は安全のため `True`（無効）になっています。実際にAI機能を利用する際は、必ず **`False`** に書き換えてください。
   * **`OLLAMA_API_URL`**: Ollamaが動作しているエンドポイントのURLを指定します。
     * **DockerコンテナからホストのOllamaを叩く場合**: `'http://host.docker.internal:11434/api/generate'` (初期値)
     * **Dockerを使わず、ローカルPC上で直接システムを実行する場合**: `'http://localhost:11434/api/generate'` に書き換えてください。
   * **`OLLAMA_MODEL`**: 使用するLLMのモデル名を設定します（初期値: `'gemma4:e4b'`）。
   * **`OLLAMA_TIMEOUT`**: タイムアウト秒数（初期値: `300` 秒）。CPU実行時などレポート生成に時間がかかる場合は、`600` など長めの値を設定してください。

**7. AI予測・レポートの実行テスト**  
すべてのデータ投入とLLMの準備が完了したら、予測・レポート作成処理をテストします。
本システムでは、ブラウザ上の **「AIバッチ手動実行（490ai_batch_run.html）」画面** からボタン操作でこれらの処理を手動実行できるほか、サーバーのコマンドライン（バッチ処理）からも詳細なパラメータを指定して実行可能です。

##### A. ブラウザ画面から手動実行する場合
管理者アカウントでシステムにログインし、**「メンテナンス」 → 「AIバッチ手動実行」** 画面を開きます。
画面上のボタンをワンクリックするだけで、バックグラウンドで予測計算やLLMレポート生成処理が実行され、ダッシュボードに結果が即時反映されます。
*(※実行する前に、手順6に沿って `DISABLE_BATCH_EXECUTION` を `False` に書き換えておく必要があります)*

##### B. コマンドライン（バッチ・cron処理用）から実行する場合
サーバー上のターミナルから直接バッチ処理として呼び出します。詳細な挙動を制御するためのパラメータ（オプション引数）も用意されています。

**① Prophetによる来場者数予測の実行**
```bash
python manage.py run_forecast --periods 30
```
*   **主なパラメータ（引数）:**
    *   `--periods <整数>` : 予測する未来の日数を指定します（初期値: `30`）。
    *   `--output <ファイル名>` : ラズパイ同期用に出力するJSONのファイル名を指定します（初期値: `forecast.json`）。

**② ローカルLLM（Ollama）によるレポート生成の実行**
```bash
python manage.py run_llm_analysis --mode review
```
*   **主なパラメータ（引数）:**
    *   `--mode <review | forecast_1m | forecast_3m>` : **【必須】** 生成するレポートの種類を指定します。
        *   `review` : 当月の振り返りレポート
        *   `forecast_1m` : 翌月（1ヶ月先）の予測レポート
        *   `forecast_3m` : 3ヶ月先までの予測レポート
    *   `--ym <YYYY-MM>` : 分析・予測の基準となる年月を指定します（初期値: 実行時の当月）。
    *   `--model <モデル名>` : 一時的に別のモデル（例: `qwen2.5:7b`）を指定して実行したい場合に使用します。
    *   `--stream` : レポートがテキスト出力される様子をコマンドライン上にリアルタイムにストリーミング表示します。

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

### 気象観測地点マスタの再生成（通常は不要）
```bash
python manage.py gen_weather_station_master
```
気象庁サイトから全国の観測地点一覧（気象官署／アメダス）を取得し、
`containers/postgres/sql/02_tz103_setup.sql` を生成します。

このSQLは生成済みのものをリポジトリに同梱しているため、**通常の導入・運用では実行する必要はありません。**
気象庁の観測地点が新設・廃止された場合や、地点一覧ページの構造が変わった場合にのみ実行してください。

| オプション | 既定値 | 内容 |
| :--- | :--- | :--- |
| `--out` | `containers/postgres/sql/02_tz103_setup.sql` | 出力先のSQLファイル |
| `--sleep` | `1.0` | 気象庁サイトへのアクセス間隔（秒） |
| `--timeout` | `15` | HTTPタイムアウト（秒） |

Note: 都府県・地方ごとに1ページずつ取得するため、完了までに1分程度かかります。
気象庁のサーバーに負荷をかけないよう、`--sleep` は既定値のまま実行してください。

生成後は、既存のデータベースへ反映させる必要があります（DB初期化SQLはコンテナの初回起動時にしか実行されません）。
`containers/postgres/sql` は db コンテナの `/docker-entrypoint-initdb.d` にマウントされているため、
そのパスを `-f` で指定します。
```bash
docker compose exec db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -f /docker-entrypoint-initdb.d/02_tz103_setup.sql'
```
Note: `Get-Content ... | docker compose exec -T db psql` のようにシェルのパイプで流し込むと、
Windows PowerShell では地点名の日本語が壊れます。必ず上記の `-f` 形式を使用してください。

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