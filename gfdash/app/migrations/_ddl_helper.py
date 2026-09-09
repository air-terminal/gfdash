"""
データマイグレーションから DDL を適用するための補助。

containers/postgres/sql/ の DDL はDBコンテナの初回起動時にしか実行されない。
そのため新しいテーブルを追加しても、既に稼働している環境には作られない。

このモジュールは、テーブルが存在しない場合に限り、その DDL ファイルを
そのまま実行する。DDL の定義を Python 側へ書き写さないため、
「DDL が唯一の正」という原則を崩さずに済む。

ファイル名の頭に _ を付けているのは、Django のマイグレーションローダーに
マイグレーションとして拾わせないため。
"""

from pathlib import Path

from django.conf import settings

# containers/postgres/sql/ の位置。BASE_DIR は manage.py のある gfdash/ を指すため、
# 1つ上がリポジトリのルートになる。
SQL_DIR_PARTS = ('containers', 'postgres', 'sql')

SCHEMA_NAME = 'gf'


def sub_get_sql_path(pFileName):
    return Path(settings.BASE_DIR).parent.joinpath(*SQL_DIR_PARTS, pFileName)


def sub_table_exists(pCursor, pTableName):
    pCursor.execute(
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = %s AND table_name = %s",
        [SCHEMA_NAME, pTableName],
    )
    return pCursor.fetchone() is not None


def apply_ddl_if_missing(pSchemaEditor, pTableName, pSqlFileName):
    """
    テーブルが無ければ DDL ファイルを実行する。

    既にテーブルがある環境では何もしない。DDL の先頭には
    DROP TABLE IF EXISTS があるが、存在しない場合しか実行しないため
    既存データを消すことはない。

    DDLファイルが見つからない場合は例外にする。黙って飛ばすと、
    テーブルが無いまま起動して後続の処理が不可解な形で失敗するため。
    """
    with pSchemaEditor.connection.cursor() as cursor:
        if sub_table_exists(cursor, pTableName):
            return False

        sql_path = sub_get_sql_path(pSqlFileName)
        if not sql_path.exists():
            raise FileNotFoundError(
                f"{pTableName} が存在せず、DDL {sql_path} も見つかりません。"
                f" containers/postgres/sql/ を配置するか、DDLを手動で実行してください。"
            )

        cursor.execute(sql_path.read_text(encoding='utf-8'))

    return True
