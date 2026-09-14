"""
LLM 実行パラメータのプリセット。

このモジュールは settings.py から読み込むため、**Django に依存させないこと**。
モデルや settings を import すると、アプリのロード前に評価されて
AppRegistryNotReady になる。

プリセットは「知識」であって環境ごとの設定ではないため、.env ではなく
ここで定義する。.env では、どのプリセットを既定にするかだけを指定する。
"""

# VRAM の容量では適切な値を決められない。必要量はモデルのパラメータ数・
# 量子化・層数で大きく変わり、同じ容量でも小さなモデルなら余裕があり、
# 大規模なモデルでは本体だけでほぼ埋まる。容量を基準にした表を出すと
# 外れた値を正しいものとして使わせることになる。
#
# そのため説明文は「利用者が実際に観測できる症状」を基準にしている。
LLM_PARAM_PRESETS = [
    {
        'key': 'standard',
        'name': '1. Standard',
        'num_ctx': 4096,
        'timeout': 300,
        'think': False,
        'hint': '通常はこれを選んでください',
    },
    {
        'key': 'long_running',
        'name': '2. Long-running',
        'num_ctx': 4096,
        'timeout': 1800,
        'think': False,
        'hint': 'タイムアウトする場合（CPUオフロード・大きなモデル）',
    },
    {
        'key': 'low_memory',
        'name': '3. Low-memory',
        'num_ctx': 2048,
        'timeout': 900,
        'think': False,
        'hint': 'モデルが読み込めない、極端に遅い場合',
    },
    {
        'key': 'high_context',
        'name': '4. High-context',
        'num_ctx': 8192,
        'timeout': 900,
        'think': False,
        'hint': 'より多くの実績データを渡したい場合',
    },
    {
        # 思考は与えられた文脈を埋めるように消費されるため、本文を書く
        # 余地を残せる大きさが要る。既定の 4096 では本文が生成されない。
        'key': 'thinking',
        'name': '5. Thinking',
        'num_ctx': 16384,
        'timeout': 1800,
        'think': True,
        'hint': '多段の推論をさせる場合。相応のVRAMと時間が必要です',
    },
]

DEFAULT_PRESET_KEY = 'standard'

# どのプリセットにも一致しない組み合わせ。490画面の「個別指定」に相当する。
MANUAL_PRESET_KEY = 'manual'


def com_get_llm_presets():
    """プリセット一覧を返す"""
    return LLM_PARAM_PRESETS


def com_get_llm_preset(pKey):
    """
    キーからプリセットを返す。

    未知のキーが指定された場合は標準プリセットを返す。.env の書き間違いで
    システムが起動しなくなるより、既定の動作に倒すほうが安全なため。
    """
    for preset in LLM_PARAM_PRESETS:
        if preset['key'] == pKey:
            return preset

    for preset in LLM_PARAM_PRESETS:
        if preset['key'] == DEFAULT_PRESET_KEY:
            return preset

    return LLM_PARAM_PRESETS[0]


def com_find_llm_preset_key(pNumCtx, pTimeout, pThink):
    """
    実行パラメータの値からプリセットのキーを逆引きする。
    一致するものが無ければ 'manual' を返す。

    490画面の findLlmPreset() と同じ判定をサーバ側でも行う。コマンドは
    プリセットのキーではなく個々の値を受け取るため、実行履歴に残すには
    値から名前を引き直す必要がある。画面からキーを渡す形にしないのは、
    コマンドを直接叩いた場合や .env の既定値で動いた場合にも同じ記録が
    要るため。
    """
    for preset in LLM_PARAM_PRESETS:
        if (preset['num_ctx'] == pNumCtx
                and preset['timeout'] == pTimeout
                and preset['think'] == pThink):
            return preset['key']

    return MANUAL_PRESET_KEY
