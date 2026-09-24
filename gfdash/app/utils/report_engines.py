"""
レポートのエンジン選択と、エンジンごとの実行パラメータの既定。

司令塔(run_llm_analysis)と490画面の両方が使う。画面は「このモードで実行すると
どの値になるか」を実行前に見せる必要があり、司令塔と同じ判断をここに置く。
"""

from django.conf import settings

from . import report_forecast, report_review_single, report_review_staged

# レビューのエンジン。.env の LLM_REVIEW_ENGINE、または --review-engine で選ぶ。
# エンジンは report_common に書いた2関数を公開する
REVIEW_ENGINES = {
    'single': report_review_single,    # 軽量版。月の合計だけを1回で渡す
    'staged': report_review_staged,    # 多段版。週別・期間・天候の比較を3つの角度で読み、最後にまとめる
}
REVIEW_ENGINE_DEFAULT = 'staged'

PARAM_KEYS = ('num_ctx', 'timeout', 'think')


def com_select_review_engine(pOverride=None):
    """
    レビューのエンジンを返す。戻り値は (engine, warning)。

    設定値が不正なら既定に倒して warning に理由を入れる。止めてしまうと、
    .env の綴り1つで月次のバッチが動かなくなる
    """
    key = pOverride or getattr(settings, 'LLM_REVIEW_ENGINE', REVIEW_ENGINE_DEFAULT)
    if key in REVIEW_ENGINES:
        return REVIEW_ENGINES[key], None

    warning = (f"LLM_REVIEW_ENGINE={key!r} は不明です。{REVIEW_ENGINE_DEFAULT} を使います"
               f"（指定できる値: {', '.join(sorted(REVIEW_ENGINES))}）。")
    return REVIEW_ENGINES[REVIEW_ENGINE_DEFAULT], warning


def com_engine_for_mode(pMode, pOverride=None):
    """モードに応じたエンジン。予測は1つ、レビューは設定で選ぶ"""
    if pMode != 'review':
        return report_forecast, None
    return com_select_review_engine(pOverride)


def com_resolve_llm_params(pEngine):
    """
    明示指定が無いときの実行パラメータ（num_ctx / timeout / think）。

    優先順位は次のとおり。

        1. .env で明示した値（OLLAMA_PRESET、または OLLAMA_NUM_CTX 等の個別指定）
        2. エンジンの既定（PARAM_DEFAULTS。多段版のまとめは思考を使うので広い文脈が要る）
        3. プリセット standard の値

    エンジンの既定を .env より上に置かないのは、OLLAMA_PRESET=low_memory のような
    指定が機械の制約を表しているため。エンジンの都合でそれを上書きすると、
    読み込めないモデルを読みに行って落ちる。
    コマンドの引数と490画面の値は、この結果よりさらに優先する（呼び出し側で行う）。
    """
    explicit = getattr(settings, 'OLLAMA_PARAMS_EXPLICIT', frozenset())
    engine_defaults = getattr(pEngine, 'PARAM_DEFAULTS', {}) or {}
    base = {
        'num_ctx': getattr(settings, 'OLLAMA_NUM_CTX', 4096),
        'timeout': getattr(settings, 'OLLAMA_TIMEOUT', 300),
        'think': getattr(settings, 'OLLAMA_THINK', False),
    }

    resolved = {}
    for key in PARAM_KEYS:
        if key not in explicit and key in engine_defaults:
            resolved[key] = engine_defaults[key]
        else:
            resolved[key] = base[key]
    return resolved
