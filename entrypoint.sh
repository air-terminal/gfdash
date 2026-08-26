#!/bin/sh

# DBが立ち上がるのを少し待つ
echo "Waiting for database..."
sleep 3

# manage.py のあるディレクトリへ移動
#cd /code/gfdash 
#cd gfdash 

# 初回実行時のみ初期化処理を行う（/tmp/check フォルダの有無で判定）
if [ ! -d "/tmp/check" ]; then

    # mediaディレクトリがなければ作成する
    echo "Running media directory creation..."
    mkdir -p /code/media

    # 必要に応じて権限も付与する
    # chmod 777 /code/media

    echo "Running migrations..."
    python3 gfdash/manage.py migrate

    echo "Running collectstatic..."
    python3 gfdash/manage.py collectstatic --noinput

    # --- スーパーユーザーの自動作成 ---
    # .env に設定した環境変数を使って、対話なしで作成します
    echo "Creating superuser..."
    python3 gfdash/manage.py createsuperuser --no-input || true

    # --- 独自グループ(Manager, Staff)とテストユーザーの作成 ---
    echo "Running setup_dev_data..."
    python3 gfdash/manage.py setup_dev_data

    # 初回実行完了のマークを作成
    mkdir -p /tmp/check
    echo `date` > /tmp/check/first_setup_done
fi

echo "Starting server..."
# docker-compose.yml の command (python3 gfdash/manage.py runserver...) を実行
exec "$@"