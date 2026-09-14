"""
所見の解析を評価するためのサンプルと期待値。

どのモデルなら実用になるかを、目視ではなく数で判断するために使う。
モデルの出力を人が見比べると、印象で決まってしまい、比較のたびに
基準が揺れる。

サンプルには**施設を特定できる記述を入れないこと。** 公開版に含まれる
ファイルであり、実際の所見をそのまま置くと外部へ出る。自社の実例で
試したい場合は --remark-file を使う。

期待値は「モデルがどう答えるべきか」ではなく「間違えてはいけない点」を
書く。文章表現はモデルごとに違って構わない。
"""

# 期待値の書き方
#   min_events      最低これだけ抽出してほしい件数
#   max_events      これを超えたら分解しすぎ（None なら上限なし）
#   expect_end_none 終了日を埋めてはいけない（推測の禁止を守れているか）
#   expect_no_factor 係数を出してはいけない（数量の手がかりが無い）
#   expect_factor   係数を出してほしい（数量が明記されている）
SAMPLES = [
    {
        'key': 'period_with_rate',
        'title': '期間と数量が明記',
        'text': '10月1日から10月31日まで、近隣で大規模な工事が行われます。'
                '工事関係者の利用が見込まれ、来場者数は1割ほど増えると予想します。',
        'expect': {'min_events': 1, 'max_events': 2, 'expect_factor': True},
    },
    {
        'key': 'no_end_date',
        'title': '終了日が書かれていない',
        'text': '8月24日から近隣の施設が改修工事のため休業に入ります。'
                '再開の時期は未定です。来場者数は最大1割ほど増える可能性があります。',
        'expect': {'min_events': 1, 'max_events': 2, 'expect_end_none': True},
    },
    {
        'key': 'no_quantity',
        'title': '数量の手がかりがない',
        'text': '来月、近隣に新しい商業施設が開業する予定です。'
                '来場者数への影響がどの程度になるかは分かりません。',
        'expect': {'min_events': 1, 'max_events': 2, 'expect_no_factor': True},
    },
    {
        'key': 'multi_events',
        'title': '1つの所見に複数の出来事',
        'text': '10月上旬に近隣へ競合施設が開業する予定です。同規模の施設のため、'
                '影響は数%程度の減少と見込みます。'
                'また10月15日にボールを全数交換します。',
        'expect': {'min_events': 2, 'max_events': 4},
    },
    {
        'key': 'note_only',
        'title': '来場者数に関係しない出来事',
        'text': '9月中に事務所の空調設備を更新します。営業時間や設備の利用に'
                '影響はありません。',
        'expect': {'min_events': 1, 'max_events': 2, 'expect_no_factor': True},
    },
]


def com_get_remark_samples():
    return SAMPLES
