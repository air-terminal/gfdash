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
- **AI機能（ベータ）:** 過去の来場者数・気温の傾向より来場者数を予測する機能、及びローカルLLM(AI)より当月の振り返り、翌月の予測レポートを作成します。推論エンジンは Ollama と OpenAI互換APIの2方式に対応しています。

## Requirements (必須環境)
- Python 3.13
- PostgreSQL 18
- Django 6.0
- Docker / Docker Compose (推奨)
- prophet(AI予測機能実行時)
- Ollama、またはOpenAI互換APIを提供する推論エンジン(AIレポート作成機能実行時、VRAM8GB以上搭載のGPUでの動作推奨)
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

1ワーカーあたりのスレッド数は `GUNICORN_THREADS` で変更できます (既定 4)。
同時に処理できるリクエスト数は「ワーカー数 × スレッド数」になります。

```bash
# .env
GUNICORN_THREADS=8
```

> **スレッドを使う理由**
> ワーカークラスに `gthread` を指定しています。gunicorn 既定の `sync` は
> リクエストの処理中にハートビートを返さないため、`--timeout` (既定 120 秒) を
> 超える処理が強制終了されます。AIレポート生成のように時間のかかる処理が
> これに該当し、画面上はエラーも出ずに出力が途切れます。
> `gthread` は別スレッドでハートビートを送るため、長い処理を通しながら
> ワーカーのハング検出も維持できます。

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

**6. AIレポートのセットアップ**  
ローカルLLMを用いたAIレポート機能を使用するには、以下の設定が必要です。

推論エンジンは2つの方式に対応しています。どちらか一方を用意してください。

| 方式 | `LLM_PROVIDER` | 対象 |
| :--- | :--- | :--- |
| Ollama ネイティブAPI | `ollama`（初期値） | Ollama |
| OpenAI互換API | `openai` | llama.cpp server / vLLM / LM Studio / [FreeToken](https://github.com/FlashML-org/FreeToken) など |

1. **推論エンジンの起動とモデルの準備**

   **A. Ollama を使う場合**

   ローカルにOllamaをインストール・起動し、あらかじめ対象のLLMモデルをPull（ダウンロード）しておきます。
   ```bash
   ollama pull gemma4:e4b
   ```
   *(※別のモデル、例えば `qwen2.5:7b` などを使用する場合は、そちらをPullしてください)*

   **B. OpenAI互換APIの推論エンジンを使う場合**

   お使いのエンジンの手順に従って起動し、モデルを読み込んでおきます。導入方法は
   製品ごとに異なるため、本システムでは扱いません。本システムが必要とするのは
   **OpenAI互換のエンドポイントのURLだけ**です。

   起動できたら、接続できるか事前確認しておくとトラブル時の切り分けが楽になります。
   ```bash
   curl http://localhost:8080/v1/models
   ```
   モデルの一覧がJSONで返れば準備完了です。この `/v1` までのURLを
   `OPENAI_API_BASE` に設定します。

   なお、コンテキスト長と思考の切り替えは**OpenAI互換API推論エンジン側の設定に従います**
   （画面やパラメータからは指定できません）。必要な場合はエンジンの起動オプションで
   調整してください。

2. **設定ファイル（gfdash/settings.py または .env）の変更**  
   環境に合わせて、以下の項目を調整します。
   * **`DISABLE_BATCH_EXECUTION`**: AIバッチ処理（予測やLLMレポート生成など）の無効化フラグです。初期値は安全のため `True`（無効）になっています。実際にAI機能を利用する際は、必ず **`False`** に書き換えてください。
   * **`LLM_PROVIDER`**: 使用する推論エンジンのAPI方式（初期値: `ollama`）。
     * `ollama` … Ollama のネイティブAPIを使います。従来どおりの動作です。
     * `openai` … OpenAI互換APIを使います。[FreeToken](https://github.com/FlashML-org/FreeToken) / llama.cpp server / vLLM / LM Studio など、OpenAI互換のエンドポイントを提供する推論エンジンで動作します。
     * 互換API側では**コンテキスト長と思考の切り替えをリクエストで指定できません**（推論エンジン側の設定に従います）。該当する入力欄は画面上で無効化されます。
   * **`OPENAI_API_BASE`**: OpenAI互換APIの接続先（`LLM_PROVIDER=openai` のとき）。`/v1` まで含めて指定します。
   * **`OPENAI_API_KEY`**: 同上の認証キー。ローカルの推論エンジンでは不要なことが多く、空のままで構いません（空の場合は認証ヘッダを送りません）。
   * **`OLLAMA_API_URL`**: Ollamaが動作しているエンドポイントのURLを指定します（`LLM_PROVIDER=ollama` のとき）。
     * **DockerコンテナからホストのOllamaを叩く場合**: `'http://host.docker.internal:11434/api/generate'` (初期値)
     * **Dockerを使わず、ローカルPC上で直接システムを実行する場合**: `'http://localhost:11434/api/generate'` に書き換えてください。
   * **`OLLAMA_MODEL`**: 使用するLLMのモデル名を設定します（初期値: `'gemma4:e4b'`）。方式に関わらず、この項目でモデルを指定します。
   * **`OLLAMA_PRESET`**: LLM実行パラメータのプリセット（初期値: `standard`）。通常はこれだけを指定すれば十分です。
     * 指定できる値と内容は次のとおりです。

       | 値 | 用途 | num_ctx | タイムアウト | 思考 |
       | :--- | :--- | ---: | ---: | :---: |
       | `standard` | 通常はこれ | 4096 | 300秒 | 無 |
       | `long_running` | タイムアウトする場合 | 4096 | 1800秒 | 無 |
       | `low_memory` | モデルが読み込めない、極端に遅い場合 | 2048 | 900秒 | 無 |
       | `high_context` | より多くの実績データを渡したい場合 | 8192 | 900秒 | 無 |
       | `thinking` | 多段の推論をさせる場合 | 16384 | 1800秒 | 有 |

     * 下記の個別設定を書いた場合は、そちらがプリセットより優先されます。プリセットで運用する場合は個別設定をコメントアウトしてください。
     * AIバッチ実行画面(490)からは、実行のたびに一時的に変更することもできます。
   * **`OLLAMA_TIMEOUT`**: タイムアウト秒数（初期値: プリセットの値）。CPU実行時などレポート生成に時間がかかる場合は、`600` など長めの値を設定してください。
   * **`OLLAMA_NUM_CTX`**: LLMが確保する記憶領域のトークン数（初期値: `4096`）。値を上げるとより多くの実績データをプロンプトに含められますが、VRAMの使用量も増えます。モデルが読み込めない場合は `2048` などに下げてください。
     * **`LLM_PROVIDER=openai` では使用されません。** 推論エンジン側の設定に従います。
     * 適切な値はVRAM容量だけでは決まりません。同じ容量でも、小さなモデルなら余裕があり、大規模なモデルでは本体だけでほぼ埋まります。AIバッチ実行画面(490)に症状から選べるプリセットを用意しているので、そちらもご利用ください。
   * **`OLLAMA_THINK`**: 思考（thinking）を有効にするかどうか（初期値: `False`）。
     * **`LLM_PROVIDER=openai` では使用されません。** 推論エンジン側の設定に従います。
     * 思考に対応したモデルを使う場合のみ意味を持ちます。非対応のモデルには送信されません。
     * **有効にする場合は `OLLAMA_NUM_CTX` も併せて広げてください。** 思考は与えられたコンテキストを埋めるように消費するため、余裕が無いと本文が生成されないまま終わります（レポートが空になります）。
     * 現在のレポートは集計済みの数値を定型の見出しに沿って記述するもので、多段の推論を必要としません。そのため初期値では無効にしています。
   * **`ENABLE_HOLIDAY2`**: 第2休日カレンダーを使用するかどうか（初期値: `False`）。
     * 国民の祝日とは異なる休日体系を持つ顧客層（近隣の主要事業所など）があり、その休日が来場者数に影響する場合に `True` にしてください。祝日とも曜日とも一致しないため、通常の予測では説明できない変動を捉えられます。
     * 有効にすると、カレンダーの名称を `tz901_com_name` の code:008 に設定できます。名称を入れた枠だけが使用中として扱われます。
     * 該当する顧客層が無い環境ではそのまま `False` で構いません。画面にも予測処理にも現れません。
   * **`ALLOW_PAST_CALENDAR_EDIT`**: 「休業・祝日カレンダー」画面(913)で過去日を編集できるようにするかどうか（初期値: `True`）。
     * 通常はそのままで構いません。過去日の休業実績をあとから補完できます。
     * 来場実績を外部システム（Access等）から取り込んでいる場合、過去日はそちらが正となり、画面で編集しても取り込みのたびに上書きされます。誤入力を防ぎたい場合は `False` に設定すると、過去日を編集できなくなります。

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

*   **計画休業の反映について:**
    休業・祝日カレンダー（画面913）で「計画」として登録された時間帯休業は、
    予測値に営業時間ぶんの補正が掛かります。終日休業なら 0 になります。
    補正の割合は自社の過去実績から自動で算出されるため、設定は不要です。
    実績が少ない環境では時間帯の単純按分にフォールバックします。

    台風接近などの天候起因で登録された休業は、将来について予見できないため
    補正の対象外です。この区別は `temp_closed` のビットで行っています
    （[docs/codes.md](docs/codes.md) を参照）。

**② ローカルLLMによるレポート生成の実行**
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

### 来場者数の取り込み

来場者数のCSVを取り込みます。**AI機能（予測・レポート）はこのデータだけで動作します。**

画面から取り込む場合は、**「メンテナンス」→「来場者数アップロード」**（990）を開き、
CSVをドラッグ＆ドロップしてください。「内容を確認」で登録せずに件数と注意点だけを
確認できます。

コマンドから取り込む場合は次のとおりです。

```bash
python manage.py import_attendance attendance.csv --dry-run
python manage.py import_attendance attendance.csv
```

**1行目に列名を書きます。列の順序は問いません。**

```csv
business_day,morning,afternoon,night,member,visitor,school_total
2026-01-15,45,38,62,52,93,12
```

| 列 | 内容 |
| :--- | :--- |
| `business_day` | 営業日（**必須**）。`YYYY-MM-DD` または `YYYY/MM/DD` |
| `morning` / `afternoon` / `night` | 午前・日中・夜の来場者数 |
| `member` / `visitor` | メンバー・ビジター人数 |
| `int_school` / `ext_school` / `school_total` | 内部・外部スクールと合計 |
| `early_morn` / `late_night` | 早朝・深夜（予約枠。通常は不要） |

**必要な列だけを書けば足ります。** 記録していない項目は省略でき、書かなかった列の
値は変更しません。既に登録済みの日に対して一部の列だけを更新することもできます。

同じ日を2度取り込んでも行は増えず、内容が更新されます。

書式の誤りは行番号を添えて報告します。取り込めない列名があった場合も知らせるので、
綴り間違いに気づけます。

雛形として [`demo_data/sample_attendance.csv`](./demo_data/sample_attendance.csv) を
同梱しています。

> **整合性の確認について**
>
> 「時間帯別の合計」と「メンバー＋ビジター」、「スクールの内訳」と「スクール合計」が
> 一致しない場合は警告を表示しますが、取り込みは中断しません。記録している項目は
> 施設によって異なるためです。どちらか一方しか記録していない場合（もう一方が0）は
> 確認の対象外です。

### 第2休日カレンダーの取り込み・書き出し

`.env` の `ENABLE_HOLIDAY2` を `True` にした場合に使用します。

```bash
python manage.py import_holiday2 holiday2.csv
python manage.py export_holiday2 --output holiday2.csv
```

CSVは日付を範囲で指定できます。工場の操業カレンダーなどは連休のかたまりが
大半なので、1日ずつ書かずに済みます。書き出しも同じ形へ圧縮するため、
往復しても行数は増えません。

```csv
calendar_cls,from_day,to_day,day_cls,memo
1,2026-08-11,2026-08-16,1,夏季連休
1,2026-09-21,2026-09-23,2,祝日だが稼働
1,2026-06-19,,,創立記念日
```

| 列 | 内容 |
| :--- | :--- |
| `calendar_cls` | カレンダー種別。`tz901` code:008 の枝番に対応 |
| `from_day` | 開始日 (YYYY-MM-DD) |
| `to_day` | 終了日。空なら単日 |
| `day_cls` | 1:休日 / 2:稼働日。空なら 1 |
| `memo` | 連休の名称など（任意） |

**行が必要なのは「通常の週パターンと食い違う日」だけです。** 土日を休日として
登録する必要はありません。曜日の効果は予測モデルの週次季節性が既に学習しており、
重複して与えると精度がかえって下がります。

`.env` で `ENABLE_HOLIDAY2_FORECAST=True` を設定すると、来場者予測
（`run_forecast`）で次の2つの回帰変数に変換されます。国民の祝日は自動判定
するため、登録は不要です。

| 変数 | 条件 | 例 |
| :--- | :--- | :--- |
| `h2_<種別>_off` | 第2休日で休み、かつ通常は稼働（平日） | 夏季連休の平日 |
| `h2_<種別>_work` | 第2休日で稼働、かつ通常は非稼働（土日・祝日） | 祝日の操業日 |

土日や祝日の休みは変数になりません。週次季節性・祝日効果と重複するためです。

> **有効にする前に、来場実績の全期間ぶんを登録してください**
>
> 一部の期間しか登録していないと、**未登録の期間が「第2休日ではなかった」と
> 誤って学習されます。** 係数が薄まり、精度はかえって落ちます。データが無い
> より悪い状態になるため、既定を無効にしています。
>
> 開発環境での実測結果です。
>
> | 登録範囲 | 検証件数 | 全体の誤差 |
> | :--- | ---: | :--- |
> | 実績の全期間（13年8か月） | 1169 | **0.6% 改善** |
> | 直近のみ（2年8か月） | 420 | 1.0% 悪化 |
>
> 全期間を登録した場合、第2休日に該当しない日の誤差も改善しました。連休の
> 影響を年次季節性が吸収しようとして生じていた歪みが、専用の変数に分離された
> ためと考えられます。
>
> 登録データ自体は無効のままでも保持され、画面表示には使われます。

`day_cls=2`（稼働日）は「通常は休みだが操業している日」です。土曜の振替出勤の
ほか、**祝日が操業日になっている場合**に使います。

| オプション | 内容 |
| :--- | :--- |
| `--dry-run` | DBを更新せず、取り込まれる内容だけを表示（取込） |
| `--replace` | 対象カレンダーの既存データを削除してから取り込む（取込） |
| `--calendar <整数>` | 特定のカレンダー種別だけを書き出す（書出） |
| `--from-day <日付>` | 指定日以降だけを書き出す（書出） |

`--replace` は連休の期間を縮める場合に使います。通常の取り込みは指定した日付を
追加・更新するだけなので、CSVから消した日付はDBに残ります。

Note: 複数の環境で同じカレンダーを使う場合、書き出したCSVを配布して取り込みます。
コマンドなのでcronで自動化できます。

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