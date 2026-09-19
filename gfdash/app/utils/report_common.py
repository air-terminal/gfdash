"""
AIレポート生成の各エンジンが共有するもの。

エンジン（report_review_single / report_forecast / 今後の report_review_staged）は
同じ形の2関数を公開し、run_llm_analysis はエンジンの中身を知らずに呼ぶ。

    com_build_context(pMode, pBaseMonth, pCustomText) -> dict
        LLM を呼ばずに、プロンプトと所見の複製を組み立てる。
        {'prompts': [{'name': ..., 'text': ...}, ...],
         'remark_snapshot': [...]}      # tz310.applied_remark_json に残す内容

    com_generate(pClient, pModel, pParams, pContext, pOnText, pOnThink) -> ReportResult
        LLM を呼んでレポート本文を返す。

プロンプトの文面は各エンジンが持ち、ここには置かない。
"""

import os

from django.conf import settings


class ReportResult:
    """
    エンジンの戻り値。方式（1回で書く／段を分ける）によらず同じ形にそろえる。

    stage_outputs は段を分けるエンジンだけが埋める。[{'name': ..., 'text': ...}]。
    1回で書くエンジンでは空。
    """

    def __init__(self, pText='', pThinkText='', pStats=None, pStageOutputs=None):
        self.text = pText
        self.think_text = pThinkText
        self.stats = pStats or {}
        self.stage_outputs = pStageOutputs or []


# 全エンジン共通の前置き。
#
# 提案・助言の禁止を固定にしているのは、運用で「提案の部分が最もハルシネーションを
# 起こしやすく、そこが崩れるとレポート全体が信用されなくなる」ことが分かっているため。
# 以前は「悪化しているときだけ簡潔に」としていたが、その条件付きの許可が想像の入口に
# なっていた。
COMMON_RULES = """【厳守】
- 提供された数値以外のデータを作らないでください。書かれていない原因や出来事を推測して補わないでください。
- いかなる場合も、業務改善の提案・アドバイス・スタッフへの指示を出力しないでください。純粋な数値の分析と事実の総括のみを行ってください。"""


def com_build_common_header(pCustomText):
    """
    役割の宣言、施設プロファイル（独自プロンプト）、共通ルールを並べる。

    独自プロンプトは custom_prompts/<mode>.txt の中身で、施設の打席数などの
    プロファイルと、利用者が足したい指示の置き場。無ければその段落を省く。
    """
    parts = ['あなたはゴルフ練習場の運営データを扱うアシスタントです。']

    custom = (pCustomText or '').strip()
    if custom:
        parts.append('【この施設について】\n' + custom)

    parts.append(COMMON_RULES)
    return '\n\n'.join(parts)


def com_load_custom_prompt(pMode):
    """
    独自プロンプトを読む。戻り値は (text, error)。

    無いのは正常（公開版の既定）。読めなかったときだけ error に理由を入れ、
    呼び出し側が警告として出す。ここで stderr に書かないのは、エンジンの
    関数を画面やテストからも呼べるようにするため。
    """
    path = os.path.join(getattr(settings, 'LLM_CUSTOM_PROMPT_DIR', ''), f'{pMode}.txt')
    if not os.path.exists(path):
        return '', None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read(), None
    except Exception as e:
        return '', f'カスタムプロンプトの読み込みに失敗しました: {e}'


def com_generate_single(pClient, pModel, pParams, pPrompt, pOnText, pOnThink):
    """
    1回の生成でレポートを書くエンジンの共通部分。

    pParams は {'num_ctx', 'timeout', 'think', 'stream'}。think は推論エンジンが
    対応しないとき None を渡すこと（クライアント側で送らない）。
    """
    result = pClient.generate(
        pPrompt, pModel, pParams['num_ctx'], pParams['timeout'],
        pParams['think'], pParams['stream'], pOnText, pOnThink,
    )
    return ReportResult(result.text, result.think_text, result.stats)
