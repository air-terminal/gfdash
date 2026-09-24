"""
月次レビューレポート・多段版。

同じ月を3つの角度（来場者推移 / 天候 / 外部要因）で別々に読ませ、最後に
まとめる。1回で書く軽量版(report_review_single)は月の合計しか渡せず、月の中で
何が起きたかを語れない。合計しか無いのに推移を書かせると想像で埋める。

段1〜3は互いの出力を見ない。段4だけが統合する。各段の出力は箇条書きの
事実のみで、数値は提供データのまま引用させる。段4に渡す数値表はコードが
作り、LLM には書き換えさせない。

設計: gfdash-ops/docs/llm-report-staged-design.md
"""

import re

from ..models import Tz305MonthlyRemark
from .com_remark import com_build_remark_section
from .report_common import ReportResult, com_build_common_header
from .report_data import (
    com_collect_review_data, com_render_attendance_block, com_render_daytype_table,
    com_render_headline_table, com_render_weekly_table,
)
from .report_weather import (
    EVENT_GROUPS, com_render_weather_block, com_render_weather_table, sub_baseline_years,
)

ENGINE_NAME = 'staged'

# v1.0.0: 初版。段の構成と文面を変えたらここを上げる。
#         段ごとの細かい調整も同じ版で管理する（履歴に残るのはこの1つ）。
#         用語の統一（振り返り→レビュー）でも版は上げない。まだ公開して
#         いないので、v1.0.0 として出るのは統一後の文面だけ
PROMPT_VERSION = 'v1.0.0'

# このエンジンの実行パラメータの既定。.env の明示指定と引数・画面の値が優先する
# （report_engines.com_resolve_llm_params）。
#
# まとめの段は観察を結びつけて分析総括を書くので thinking を使う。thinking は
# コンテキストを埋めるように消費し、段4のプロンプトは 2,000 トークン前後ある。
# 8192 では 26B 級の thinking（6,000〜10,000 トークン）で本文の余地が無くなり、
# ほぼ毎回やり直しになったため 16384 を既定にする。段1〜3は thinking を
# 使わないので、広げた分の負担はまとめの段の1回だけ。
# timeout は変えない（1回の生成の上限で足りる）
PARAM_DEFAULTS = {'num_ctx': 16384, 'think': True}

# 段4で「会員台帳の確認を」と添える条件。メンバー来場の前年同月比が
# この月数以上続けてマイナスのときだけ。回数の減少が人数の減少か頻度の
# 低下かはこのシステムでは分からないので、判断ではなく次に見る場所の案内に留める
MEMBER_DECLINE_MONTHS = 3

STAGE_ATTENDANCE = 'attendance'
STAGE_WEATHER = 'weather'
STAGE_FACTORS = 'factors'
STAGE_SUMMARY = 'summary'

# 段4のテンプレートで、段1〜3の出力を差し込む印。
# str.format を使わないのは、施設プロファイルや所見に波括弧が入ると壊れるため
TOKEN_ATTENDANCE = '<<attendance>>'
TOKEN_WEATHER = '<<weather>>'
TOKEN_FACTORS = '<<factors>>'

NO_REMARK_TEXT = '確定済みの所見はありません。'

# 思考なしでまとめをやり直したときにログへ出す文。[think-fallback] は画面(490)が
# 拾う印で、処理の終了後にダイアログで知らせる。文言を変えても印は残すこと
THINK_FALLBACK_MARK = '[think-fallback]'

# 段4の見出し。段4の出力に見出しを見つけて、その下に数値の表を置く
HEADING_HEADLINE = '予測と実績・前年比較'
HEADING_DAYTYPE = '時間帯別の動向'
HEADING_WEATHER = '天候の影響考察'
HEADING_FACTORS = '運営上の出来事'
HEADING_OVERALL = '総括'


def com_build_context(pMode, pBaseMonth, pCustomText):
    data = com_collect_review_data(pBaseMonth)
    header = com_build_common_header(pCustomText)
    ym = pBaseMonth.strftime('%Y年%m月')

    remark_section, remark_snapshot = com_build_remark_section(
        [pBaseMonth], Tz305MonthlyRemark.REMARK_CLS_REVIEW)

    prompts = [
        {'name': STAGE_ATTENDANCE, 'text': sub_prompt_attendance(header, ym, data)},
        {'name': STAGE_WEATHER, 'text': sub_prompt_weather(header, ym, data)},
    ]
    # 所見が無ければ段3は飛ばす。空の材料で「整理しろ」と言うと、無いものを
    # 作り出す。段4には「所見なし」と伝える
    if remark_section:
        prompts.append({'name': STAGE_FACTORS, 'text': sub_prompt_factors(header, ym, remark_section)})

    table = com_render_headline_table(data)
    prompts.append({'name': STAGE_SUMMARY, 'text': sub_prompt_summary(header, ym, data, table)})

    return {
        'prompts': prompts,
        'remark_snapshot': remark_snapshot,
        'has_remark': bool(remark_section),
        'headline_table': table,
        # 見出しの下に置く表。文章が引く数値の根拠を、同じ数値から作った表で示す。
        # LLM には渡さない（渡すと書き写して冗長になる）。生成後にコードで置く
        'section_tables': [
            (HEADING_HEADLINE, com_render_weekly_table(data)),
            (HEADING_DAYTYPE, com_render_daytype_table(data)),
            (HEADING_WEATHER, com_render_weather_table(data['weather'], data['prev_month'])),
        ],
    }


# ----------------------------------------------------------------------
# 段ごとのプロンプト
# ----------------------------------------------------------------------

# 段1〜3に共通の形。因果を書かない・日付を並べない規則は段1・2だけに付ける。
# 段3は運営者の所見（出来事の日付と見立て）を整理する段なので、同じ規則を
# 付けると出来事の名前や見立てまで落とす
STAGE_RULES = """【出力の形】
- 前置きや見出しは付けず、箇条書き（・）だけを出力してください。
- 数値は提供データにある値（平均・差・前年比）をそのまま引用してください。自分で計算した数値を書かないでください。"""

DATA_STAGE_RULES = """- 「多い」「少ない」「増えた」「減った」までで止め、理由や原因は書かないでください。
  データに事実（猛暑日・雨・休業など）が添えてある場合も、並べて書くだけにして
  「◯◯が要因」「◯◯のため」と結び付けないでください。結び付けるのはまとめの段の仕事です。
- 日付を並べて書かないでください。週・期間・平日/休日のまとまりで述べてください。
  ただし予測とのずれのように、データが日付つきで示している事柄はそのまま書いて構いません。"""


def sub_prompt_attendance(pHeader, pYm, pData):
    return f"""{pHeader}

【作業】
{pYm} の来場者数の推移を、次のデータから事実として箇条書きにしてください。
比較（前年比・差）はデータに付けてあります。数値を読んで「どちらが多かったか」を述べてください。

{com_render_attendance_block(pData)}

{STAGE_RULES}
{DATA_STAGE_RULES}
- 次の5点を、それぞれ1〜2行で書いてください。
  1. 週ごとの動き（どの週が多く、どの週が少なかったか。予測を上回った週・下回った週、前年比で伸びた週・落ちた週）。予測から大きくずれた週があれば、どの日がずれを作ったかと、その日の事実を並べて書く（例: 「07/16 -20%（猛暑日）」）。「◯◯が要因」「◯◯のため」とは書かない
  2. 日の区分（平日・土日・祝日・データにあるその他の休日区分）ごとの差と、それぞれの前年比
  3. 時間帯（朝・昼・夜）のどこが伸び、どこが落ちたか。区分で違いがあればそれも
  4. 期間のまとまり（連休・特別営業・休日カレンダーの期間）が、比べる相手の平均より多かったか少なかったか
  5. 客層（メンバー／ビジター）の前年との違いと、メンバーの前年同月比の並び（何か月続けてマイナスか）
- 休業日は「休業日」として扱ってください。休業日の来場の少なさを不振と読まないでください。
- データが「該当なし」の観点は、その行ごと書かないでください（「該当なし」とも書かない）。
- 全体で最大10行。"""


def sub_prompt_weather(pHeader, pYm, pData):
    weather = pData['weather']
    # 発生したら取り上げる群（強風・猛暑日・冬日・雪）は、材料にある月だけ観察点にする。
    # 無い月に聞くと「猛暑日は0日で前年と同等」という読む価値の無い行が出る
    points = [
        '雨のあった日の来場が、同じ区分の雨なしの日と比べてどうだったか（当月と前年）',
        '時間帯別に、雨のあった時間帯の来場がどうだったか。朝・昼・夜で効き方に違いがあればそれも',
        '強い雨の日があれば、その来場がどうだったか',
    ]
    shown_names = [name for key, name, _m in EVENT_GROUPS if weather['shown'][key]]
    if shown_names:
        points.append('・'.join(shown_names) + 'の来場が、そうでない日と比べてどうだったか'
                      + ('。強風の日は、参考行にある瞬間風速・風の強い時間とその最大風速・風向・その時間の雨量を、'
                         '日付を除いてそのまま添える（施設の条件と突き合わせるため）'
                         if weather['shown']['wind'] else ''))
    years = sub_baseline_years(weather)
    compare_to = f'前年同月・過去{years}年の同月平均' if years else '前年同月'
    points.append(f'{compare_to}と比べて、気温が高かったか低かったか、雨の日数・強い雨'
                  + ('・' + '・'.join(shown_names) if shown_names else '') + 'の日数が多かったか少なかったか')
    numbered = '\n'.join(f'  {i}. {text}' for i, text in enumerate(points, start=1))

    return f"""{pHeader}

【作業】
{pYm} の天候と来場者数の関係を、次のデータから事実として箇条書きにしてください。
天候の判定と群ごとの平均はデータに付けてあります。数値を読んで「どちらが多かったか」を述べてください。

{com_render_weather_block(weather, pData['prev_month'])}

{STAGE_RULES}
{DATA_STAGE_RULES}
- 次の{len(points)}点を、それぞれ1〜2行で書いてください。
{numbered}
- 「雨だから減った」のような因果の断定はせず、「雨の日は…だった」の形で書いてください。
- 例年との比較は「過去N年の平均」と年数を添えて書き、「例年」と言い切らないでください。
- 日数の差が2日以内（0日と1日、1日と2日など）は「ほぼ同じ」と書き、増えた・減ったと言わないでください。差（%）が付いていない群は、日数だけを書いてください。
- 差（%）が ±5% 以内のときは「ほぼ変わらない」と書き、多かった・少なかったと言わないでください。
- 気温は「高い／低い」、日数は「多い／少ない」と書いてください。
- 日付の参考行は判定の確認用です。出力に日付を書かないでください。
- 全体で最大8行。"""


def sub_prompt_factors(pHeader, pYm, pRemarkSection):
    return f"""{pHeader}

【作業】
{pYm} について運営者が残した所見を、レポートに使う形に整理してください。
{pRemarkSection}
{STAGE_RULES}
- 出来事ごとに1行。出来事の名前、日付（期間）、来場者数への影響の向き（増・減・読めない）を必ず残してください。
- 所見に書かれた見立てや理由は、「運営者は…と見ている」の形でそのまま残してください。運営者の見立てを削らないでください。
- 所見に書かれていないことを足さないでください。
- 全体で最大8行。"""


def sub_prompt_summary(pHeader, pYm, pData, pTable):
    decline = sub_member_decline_months(pData)

    notice = ''
    if decline >= MEMBER_DECLINE_MONTHS:
        notice = (f"\n■ 客層の注意\nメンバー来場の前年同月比は直近 {decline} か月続けてマイナスです。\n")

    return f"""{pHeader}

【作業】
{pYm} の「月次レビューレポート」を Markdown で作成してください。
材料は次のとおりです。

■ 数値表
{pTable}
{notice}
■ 来場者推移の観察
{TOKEN_ATTENDANCE}

■ 天候の観察
{TOKEN_WEATHER}

■ 運営上の出来事
{TOKEN_FACTORS}

【出力の形】
1. 次の5つの見出し（###）で構成してください。見出しの文言はこのとおりにしてください。
   - {HEADING_HEADLINE} … 冒頭に上の数値表を置き、続けて月全体の動きと客層（メンバー／ビジター）を文章で。週ごとの動きと、期間のまとまり（連休・特別営業・休日カレンダーの期間）もここに書く。予測から大きくずれた週が観察にあれば、どの日がずれを作り、その日に何があったかに触れる
   - {HEADING_DAYTYPE} … 朝・昼・夜のどこが伸び、どこが落ちたか。日の区分（平日・土日・祝日・観察にあるその他の休日区分）の違い。週や期間のまとまりの話はここに書かない
   - {HEADING_WEATHER} … 雨（時間数・強さ・時間帯）の来場への効き方と、観察にある群（強風・猛暑日・冬日・雪のうち、観察に出ているものだけ）。**観察に出ていない群の名前を出さないでください**（例: 観察に猛暑日が無ければ猛暑日に触れない）。この見出しの【分析総括】は、前年同月や過去N年の平均と比べて天候面の支障が大きかった月か小さかった月かで締める。ただし群によって向きが違うときは「◯◯は平均より少なかったが、△△は多かった」と**群ごとに分けて**述べ、まとめて「多かった」「少なかった」と書かない。平均より多い群が1つでもあれば「支障は小さかった」と言い切らない。天候を来場者数の増減の理由に断定しない
   - {HEADING_FACTORS} … 出来事ごとに、期間と来場への影響と運営者の見立て
   - {HEADING_OVERALL} … 月全体を3〜4文で。上の4つの見出しの分析総括をつなげて、この月をどう読むか
2. 最初の4つの見出しは、それぞれ2つの段落で書いてください。
   - 1つ目の段落: 観察を2〜3文に要約した文章（書き写さない）。「事実:」のようなラベルは付けず、文章から始めてください
   - 2つ目の段落: 1つ目の段落との間に空行を1行置き、「**【分析総括】**」で始めて、1つ目の段落をつなげて読める1〜2文。例: 「【分析総括】雨の日は前年より多かったが、雨の日の平均は雨でない日と差が小さく、天候の影響は限定的と読める」
3. 【分析総括】で書いてよいのは、観察どうしを結びつけた読みと、所見にある運営者の見立て（「運営者は…と見ている」）、それに冒頭の【この施設について】に書かれた施設の条件・運用制限を観察に当てた読みです。施設の条件を当てるときは、**その条件のすべての要素（風向・風速・雨量・時刻など）を観察の数値で確かめてから**にしてください。1つでも確かめられない要素があれば、その条件には触れないでください。**確かめた結果その条件に当てはまらなかったときも、その条件について何も書かないでください**（「該当しませんでした」「条件は重なりませんでした」のような否定形も書かない）。同じ日の別の時刻の値どうしを組み合わせないでください（風が強かった時間と雨が降った時間が違えば、その条件は成立しません）。観察・所見・施設の条件に無い出来事や数値を持ち込まないでください。観察に無いことは「データからは読み取れない」として構いません。
4. **数値表は Markdown の表のまま、一字も変えずに置いてください。** 表は要約の対象ではなく、省略しないでください。
5. 文章で引用する数値は、数値表の値と、観察にある代表的な値（平均・前年比）に限ってください。1つの見出しの文章で引用する数値は3つまでにしてください。
6. 見出しの下には、観察の元になった数値の表をシステムが後から置きます。表を自分で作らないでください（上の数値表を除く）。
7. 好調・不調にかかわらず、事実の分析と総括にとどめてください。
8. 材料に「客層の注意」がある場合だけ、「会員台帳でアクティブ会員数の確認を」と1行添えてください。それ以外の提案・助言は書かないでください。
9. 「運営上の出来事」の材料が「{NO_REMARK_TEXT}」なら、その見出しには「所見の登録はありません。」とだけ書き、【分析総括】も書かないでください。
10. 全体で 700〜1000 字程度（数値表を除く）。"""


def sub_member_decline_months(pData):
    """メンバー来場の前年同月比が、直近から何か月続けてマイナスか"""
    count = 0
    for t in reversed(pData['segments']['member_yoy']):
        if t['pct'] is None or t['pct'] >= 0:
            break
        count += 1
    return count


# ----------------------------------------------------------------------
# 実行
# ----------------------------------------------------------------------

def com_generate(pClient, pModel, pParams, pContext, pOnText, pOnThink):
    """
    段1〜3を順に生成し、その出力を段4に差し込んで最終レポートを作る。

    1段でも本文が空なら中止する。部分的な材料でまとめを書かせると、
    足りない部分を想像で埋める。
    """
    outputs = {}
    stage_outputs = []
    final_text = ''
    think_text = ''
    last_stats = {}

    total = len(pContext['prompts'])
    for index, prompt in enumerate(pContext['prompts'], start=1):
        name = prompt['name']
        text = prompt['text']

        if name == STAGE_SUMMARY:
            text = sub_fill_summary(text, outputs, pContext['has_remark'])

        sub_announce(pOnText, index, total, name)

        # 段1〜3は抽出作業で思考の恩恵が無く、文脈を埋めて本文が空になる事象を
        # 避けるため常に無効。段4だけ設定に従う
        think = pParams['think'] if name == STAGE_SUMMARY else (
            False if pClient.supports_think else None)

        result = pClient.generate(
            text, pModel, pParams['num_ctx'], pParams['timeout'],
            think, pParams['stream'], pOnText, pOnThink,
        )
        body = (result.text or '').strip()
        think_text = result.think_text
        last_stats = result.stats or {}

        if name == STAGE_SUMMARY and sub_think_exhausted(think, result):
            # 思考が文脈を使い切った。本文が空のこともあれば、書き始めてから途中で
            # 切れることもある（切れた本文は保存してはいけない）。モデルの思考の
            # 長さは銘柄で大きく違い、num_ctx を広げても伸びるだけのことがある。
            # 段1〜3の出力は生きているので、まとめだけ思考なしでやり直す
            sub_notify(pOnText, sub_fallback_notice(result))
            result = pClient.generate(
                text, pModel, pParams['num_ctx'], pParams['timeout'],
                False, pParams['stream'], pOnText, pOnThink,
            )
            body = (result.text or '').strip()
            think_text = result.think_text
            last_stats = dict(result.stats or {})
            last_stats['think_fallback'] = True

        if sub_truncated(result):
            # 途中で切れた本文は使わない。切れたまま保存すると、画面には成功と
            # 出るのに末尾の無いレポートが残る。司令塔が失敗にする
            last_stats['truncated'] = True
            return ReportResult('', think_text, last_stats, stage_outputs)

        if not body:
            # 空のまま返す。司令塔が「本文が空」として失敗にする
            return ReportResult('', think_text, last_stats, stage_outputs)

        if not pParams['stream'] and pOnText:
            # ストリームでないときも、段の出力は経過として見せる
            pOnText(body + '\n')

        if name == STAGE_SUMMARY:
            final_text = sub_separate_summary_para(sub_strip_fact_label(
                sub_ensure_table(body, pContext.get('headline_table'))))
            final_text = sub_insert_section_tables(final_text, pContext.get('section_tables') or [])
        else:
            outputs[name] = body
            stage_outputs.append({'name': name, 'text': body})

    return ReportResult(final_text, think_text, last_stats, stage_outputs)


# 段落の頭に付く「事実:」のラベル。指示で禁じても小さなモデルは付けることがある
FACT_LABEL_RE = re.compile(r'^(?:\*\*)?事実[:：](?:\*\*)?\s*', re.MULTILINE)


def sub_strip_fact_label(pText):
    """
    段落の頭の「事実:」を落とす。

    出力形を「事実」と「分析総括」の2段で説明したところ、説明の語をラベルとして
    書いた（「事実: 総来場者は…」）。読み手には要らない語なので、指示で禁じた
    うえで、それでも付いてきたらコードで落とす。【分析総括】は読み手の目印
    なので残す
    """
    return FACT_LABEL_RE.sub('', pText)


# 【分析総括】の段落。直前が空行でないと Markdown では前の段落に続いて描画され、
# 改行されたりされなかったりに見える
SUMMARY_PARA_RE = re.compile(r'(?<!\n)\n((?:\*\*)?【分析総括】)')


def sub_separate_summary_para(pText):
    """【分析総括】を必ず独立した段落にする（直前に空行を入れる）"""
    return SUMMARY_PARA_RE.sub(r'\n\n\1', pText)


def sub_ensure_table(pText, pTable):
    """
    まとめに数値表が無ければ、最初の見出しの直後に差し込む。

    「そのまま置け」と指示しても、要約の指示と競って表を落とすことがある
    （8月分の生成で丸ごと消えた）。数値表はコードが持っているので、
    LLM の出力に無ければコードで置く。あれば触らない。
    """
    if not pTable:
        return pText
    header_row = pTable.splitlines()[0]
    if header_row in pText:
        return pText

    lines = pText.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('#'):
            lines[i + 1:i + 1] = ['', pTable, '']
            return '\n'.join(lines)
    return pTable + '\n\n' + pText


def sub_insert_section_tables(pText, pTables):
    """
    見出しの下に数値の表を置く。

    文章は「朝が +27%」のように観察の数値を引くが、表が無いと読み手は根拠を
    追えない。LLM に表を作らせると数値が変わるので、観察と同じ数値から
    コードが作った表を、生成後に見出しの直後へ置く。見出しが見つからなければ
    その表は置かない（見出しの文言が変わった出力に無理に足さない）。
    「予測と実績・前年比較」は数値表が先に入っているので、その表の後ろに置く。
    """
    lines = pText.splitlines()
    for heading, table in pTables:
        index = sub_find_heading(lines, heading)
        if index is None:
            continue
        insert_at = index + 1
        # 見出し直後の空行と表（数値表）を飛ばし、その後ろに置く
        while insert_at < len(lines) and (not lines[insert_at].strip() or lines[insert_at].startswith('|')):
            insert_at += 1
        lines[insert_at:insert_at] = ['', table, '']
    return '\n'.join(lines)


def sub_find_heading(pLines, pHeading):
    for i, line in enumerate(pLines):
        if line.startswith('#') and pHeading in line:
            return i
    return None


def sub_fill_summary(pTemplate, pOutputs, pHasRemark):
    factors = pOutputs.get(STAGE_FACTORS) if pHasRemark else None
    return (pTemplate
            .replace(TOKEN_ATTENDANCE, pOutputs.get(STAGE_ATTENDANCE, ''))
            .replace(TOKEN_WEATHER, pOutputs.get(STAGE_WEATHER, ''))
            .replace(TOKEN_FACTORS, factors or NO_REMARK_TEXT))


def sub_fallback_notice(pResult):
    """
    やり直す理由と、1回目がどこで切れたかを伝える。

    打ち切った上限は推論エンジンによって違う（Ollama は num_ctx、OpenAI互換は
    サーバ起動時の設定や銘柄ごとの思考の上限）。こちらからは値が見えないので、
    実際に何トークン生成して何文字思考したかを出す。次に起きたときに
    上限の見当が付く
    """
    stats = pResult.stats or {}
    detail = [f"生成={stats.get('completion_tokens') or 0}トークン",
              f"thinking={len(pResult.think_text or '')}文字"]
    if stats.get('prompt_tokens'):
        detail.insert(0, f"プロンプト={stats['prompt_tokens']}トークン")

    return (f"⚠️ {THINK_FALLBACK_MARK} thinking が上限に達し、まとめの本文が出ませんでした"
            f"（{' / '.join(detail)}）。thinking を OFF にしてやり直します。")


def sub_truncated(pResult):
    """文脈を使い切って途中で終わったか（本文が空でも途中でも）"""
    return (pResult.stats or {}).get('finish_reason') == 'length'


def sub_think_exhausted(pThink, pResult):
    """思考ありで、文脈を使い切って終わったか"""
    return bool(pThink) and sub_truncated(pResult)


def sub_announce(pOnText, pIndex, pTotal, pName):
    if pOnText:
        pOnText(f"\n----- Stage {pIndex}/{pTotal}: {pName} -----\n")


def sub_notify(pOnText, pMessage):
    if pOnText:
        pOnText(f"\n{pMessage}\n")
