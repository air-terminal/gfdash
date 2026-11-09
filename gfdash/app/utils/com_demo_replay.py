"""
デモサイトでの AI 処理の擬似実行（記録の再生）。gitea issue #43。

公開デモには推論エンジンが無く、デモモードでは書き換えも拒否するため、490 / 480 の
AI 処理を押しても動きを見せられない。実際に AI を動かしたときの実行ログを
demo_data/replay/<key>.json に記録しておき、デモではそれを短く縮めて再生する。

再生は DB に一切触れない。デモモード（IS_SAMPLE_MODE=True）でだけ応じる。
本番の画面に擬似の実行を混ぜないため。
"""

import json
import time
from pathlib import Path

from django.conf import settings

REPLAY_DIR = Path(settings.BASE_DIR).parent / 'demo_data' / 'replay'

# 再生する操作。key は記録ファイルの名前と一致する
REPLAY_KEYS = ('490_review', '490_forecast_1m', '490_forecast_3m', '490_forecast', '480_parse')

# 縮めたあとの1回の待ちの上限（秒）。モデルの読み込みや入力の処理で、記録上は
# 1分以上なにも流れない区間がある。縮めても長く止まると、見ている人はフリーズした
# と受け取る。余った時間は文章の流れに回す
GAP_MAX = 6.0

# この長さ以上の待ちでは、待っていることを点で見せる（秒）
WAIT_SHOW = 1.0
WAIT_DOT = 0.5

# 送り出す刻み（秒）。生成中の文章は細かいチャンクで数千個届くので、1つずつ待つと
# 目標の長さに収まらない。この刻みごとに、その間に届くはずだった分をまとめて送る
TICK = 0.1


def com_demo_replay_enabled():
    """再生に応じてよい環境か。デモモードだけ"""
    return bool(getattr(settings, 'IS_SAMPLE_MODE', False))


def com_load_replay(pKey):
    """記録を読む。無ければ None"""
    if pKey not in REPLAY_KEYS:
        return None
    path = REPLAY_DIR / f'{pKey}.json'
    if not path.exists():
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def sub_fmt_seconds(pSeconds):
    seconds = int(round(pSeconds or 0))
    return f'{seconds // 60}分{seconds % 60}秒' if seconds >= 60 else f'{seconds}秒'


def sub_gaps(pChunks):
    """各チャンクの直前の待ち（記録上の秒）"""
    gaps = []
    previous = 0.0
    for chunk in pChunks:
        t = float(chunk.get('t', 0))
        gaps.append(max(0.0, t - previous))
        previous = t
    return gaps


def sub_fit_gaps(pGaps, pTotal, pTarget):
    """
    再生の待ちを決める。合計が目標の長さになるよう倍率 s を探し、各待ちを
    min(s × 待ち, GAP_MAX) にする。

    倍率を一律に掛けて長い待ち（モデルの読み込みなど）だけを GAP_MAX に詰めると、
    詰めた分だけ全体が目標より短くなる。合計が目標に合う倍率を二分法で探す。
    目標より短い記録は縮めずに、記録どおりの速さで流す。
    """
    if pTotal <= pTarget:
        return list(pGaps)

    # 1回の待ちは GAP_MAX まで。行の少ない記録（AIで解析は十数行）は目標に届かず
    # 短めに終わるが、長く止まって見えるよりよい
    cap = GAP_MAX

    def total_for(pScale):
        return sum(min(g * pScale, cap) for g in pGaps)

    # 倍率をいくら上げても目標に届かないときは、上限まで使う
    if total_for(1e9) <= pTarget:
        return [min(g * 1e9, cap) for g in pGaps]

    low, high = 0.0, 1e9
    for _ in range(100):
        middle = (low + high) / 2
        if total_for(middle) < pTarget:
            low = middle
        else:
            high = middle
    return [min(g * high, cap) for g in pGaps]


def com_replay_stream(pKey):
    """
    記録したログを、目標の長さに縮めて流すジェネレータ。StreamingHttpResponse へ渡す。

    画面は本物の実行と同じ処理でこのストリームを読む。先頭に1行だけ、擬似で
    あることを足す。デモを見た人が、本当にこの場で AI が動いたと受け取らないため。
    """
    record = com_load_replay(pKey)
    if record is None:
        yield 'この操作のデモは用意していません。\n'
        return

    chunks = record.get('chunks') or []
    total = float(record.get('total_seconds') or (chunks[-1]['t'] if chunks else 0))
    target = float(getattr(settings, 'DEMO_REPLAY_SECONDS', 20))
    gaps = sub_gaps(chunks)
    replay_gaps = sub_fit_gaps(gaps, total, target)

    # 目標より短い記録（Prophet の予測など）は縮めずに流す。そのことを書き分ける。
    # 縮めた長さは目標ではなく、実際に再生する長さを書く
    how = (f"約{sub_fmt_seconds(sum(replay_gaps))}に縮めて" if total > target else 'そのままの速さで')
    yield (f"※デモのため、{record.get('label', '')}の実行"
           f"（{record.get('model', '')}、約{sub_fmt_seconds(total)}）を"
           f"{how}再生しています。結果は保存しません。\n\n")

    # 再生の時刻（縮めたあと）を積み上げ、TICK ごとにまとめて送る。
    # 長い待ちでは、待っていることを点で見せる
    replay_clock = 0.0
    sent_at = 0.0
    buffer = []
    last_char = '\n'
    for chunk, gap in zip(chunks, replay_gaps):
        if gap >= WAIT_SHOW:
            # 待ちの前に、たまっている分を本来の時刻で送る
            if buffer:
                if replay_clock > sent_at:
                    time.sleep(replay_clock - sent_at)
                text = ''.join(buffer)
                buffer = []
                last_char = text[-1:] or last_char
                yield text
            yield from sub_wait_indicator(gap, last_char)
            last_char = '\n'
            replay_clock += gap
            sent_at = replay_clock
            buffer.append(chunk.get('text', ''))
            continue

        replay_clock += gap
        buffer.append(chunk.get('text', ''))
        if replay_clock - sent_at >= TICK:
            time.sleep(replay_clock - sent_at)
            sent_at = replay_clock
            text = ''.join(buffer)
            buffer = []
            last_char = text[-1:] or last_char
            yield text
    if buffer:
        yield ''.join(buffer)


def sub_wait_indicator(pSeconds, pLastChar):
    """
    待っている間、点を少しずつ足して見せる。記録上は何も流れない区間（モデルの
    読み込み・入力の処理）で画面が止まると、見ている人はフリーズしたと受け取る。
    本物のログには無い行なので、括弧でくくって区別する。Prophet の予測にも出るので
    「AI の応答」とは書かない
    """
    yield ('' if pLastChar == '\n' else '\n') + '（処理しています'
    steps = int(pSeconds / WAIT_DOT)
    for _ in range(steps):
        time.sleep(WAIT_DOT)
        yield '・'
    time.sleep(max(0.0, pSeconds - steps * WAIT_DOT))
    yield '）\n'
