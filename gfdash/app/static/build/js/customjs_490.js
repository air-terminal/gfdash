/*
    各画面専用javascript
    画面名：490ai_batch_run.html
*/

$(document).ready(function() {
    // カレンダーの初期化
    if (typeof($.fn.datepicker) !== 'undefined') {
        $('.input-group.date').datepicker({
            language: 'ja',
            minViewMode: 1,
            maxViewMode: 2,
            format: 'yyyy-mm', // バックエンドの引数フォーマットに合わせる
            autoclose: true
        });

    }

    // 実行パラメータはモードの既定から始める。利用者が変えるまではモードに追従する
    sub490_applyModeDefaults();
    $('#llm_mode').on('change', sub490_applyModeDefaults);

    // 月次所見の状態。対象年月を変えたら読み直す。
    //
    // イベントは component 要素(.input-group.date)側で拾う。
    // datepicker('update', date) は changeDate を出さず、component 要素に
    // change() を発火する（bootstrap-datepicker の update() の fromArgs 分岐）。
    // input に張ると前月・翌月ボタンで反応しない。input の change はここまで
    // バブルするので、component 要素で見れば全ての経路を拾える。
    $('.input-group.date').on('change changeDate', sub490_onYmChanged);
    sub490_remarkStateLoad();
});

// 直近に読み込んだ対象月。changeDate と change が両方飛ぶ場合に二重で
// 問い合わせないようにする
var gLoadedYm = '';

function sub490_onYmChanged() {
    var ym = $('#llm_ym').val();
    if (ym === gLoadedYm) { return; }
    sub490_remarkStateLoad();
}

/*
    LLM実行パラメータ
    ---------------------------------------------------------------
    gLlmPresets / gLlmParams はテンプレート側で定義している。
    プリセットの実体は app/utils/com_utils.py の LLM_PARAM_PRESETS。
*/

// どのプリセットにも当てはまらない状態を表すキー。画面上だけの選択肢で、
// サーバ側のプリセット定義には持たせない（.env で指定しても意味が無いため）
var LLM_MANUAL_KEY = 'manual';
var LLM_MANUAL_NAME = 'Manual';

// コンテキスト長のスライダー。4096刻みで止まる。
// 範囲外や刻みに合わない値は数値入力で指定でき、そのときスライダーは
// 一番近い端に寄る（数値入力の値が優先される）
var LLM_CTX_MIN = 4096;
var LLM_CTX_MAX = 65536;
var LLM_CTX_STEP = 4096;

// thinking の強さ。スライダーの 0 は「指定しない」で、1 以降が gLlmThinkEfforts の順
function sub490_effortToIndex(pValue) {
    var i = gLlmThinkEfforts.indexOf(pValue || '');
    return i < 0 ? 0 : i + 1;
}

function sub490_indexToEffort(pIndex) {
    var i = parseInt(pIndex, 10);
    return i > 0 ? (gLlmThinkEfforts[i - 1] || '') : '';
}

function sub490_effortLabel(pValue) {
    return pValue || '指定しない';
}

function sub490_ctxToSlider(pValue) {
    var n = parseInt(pValue, 10);
    if (!n) { return LLM_CTX_MIN; }
    return Math.min(LLM_CTX_MAX, Math.max(LLM_CTX_MIN, n));
}

// 現在の値に一致するプリセットを返す（無ければ null）
function findLlmPreset(numCtx, timeout, think) {
    for (var i = 0; i < gLlmPresets.length; i++) {
        var p = gLlmPresets[i];
        if (p.num_ctx === numCtx && p.timeout === timeout && p.think === think) {
            return p;
        }
    }
    return null;
}

// 利用者がダイアログで値を決めたか。決めるまではモードの既定に追従する。
// 決めた後にモードを変えても値は保つ（自分で決めた値が黙って変わらないように）
var gLlmCustomized = false;

function sub490_modeDefaults() {
    return gLlmModeDefaults[$('#llm_mode').val()] || null;
}

function sub490_applyModeDefaults() {
    var d = sub490_modeDefaults();
    if (d && !gLlmCustomized) {
        gLlmParams.num_ctx = d.num_ctx;
        gLlmParams.timeout = d.timeout;
        gLlmParams.think   = d.think;
    }
    updateLlmParamDisplay();
}

function updateLlmParamDisplay() {
    var preset = findLlmPreset(gLlmParams.num_ctx, gLlmParams.timeout, gLlmParams.think);
    var d = sub490_modeDefaults();
    var isDefault = d && d.num_ctx === gLlmParams.num_ctx
                      && d.timeout === gLlmParams.timeout && d.think === gLlmParams.think;
    // プリセットに一致すればその名前。一致しなくてもモードの既定なら「既定」と出す。
    // 多段版の既定（thinking オン・広い num_ctx）はどのプリセットにも無いが、個別指定ではない
    $('#llm_param_label').text(preset ? preset.name : (isDefault ? 'モードの既定' : LLM_MANUAL_NAME));
    $('#llm_param_ctx').text(gLlmParams.num_ctx);
    $('#llm_param_timeout').text(gLlmParams.timeout);
    $('#llm_param_think').text(
        gLlmParams.think
            ? 'ON' + (gLlmParams.think_effort ? ' (' + gLlmParams.think_effort + ')' : '')
            : 'OFF');

    // 送っていない項目は表示しない。効いていない値を出すと誤解を生む
    $('#llm_param_ctx_wrap').toggle(!!gLlmEngine.supportsNumCtx);
    $('#llm_param_think_wrap').toggle(!!gLlmEngine.supportsThink);
}

// プリセット1件分の行を組み立てる。
// 説明側にも label を付け、名前だけでなく説明をクリックしても選べるようにする。
function sub490_presetRow(pKey, pName, pHint, pValues, pChecked) {
    var id = 'dlg_llm_preset_' + pKey;
    var row = '<tr style="border-bottom: 1px solid #eee;">';

    row += '<td style="padding: 8px 10px 8px 0; vertical-align: top; white-space: nowrap;">';
    row += '<label for="' + id + '" style="font-weight: normal; margin: 0; cursor: pointer;">';
    row += '<input type="radio" id="' + id + '" name="dlg_llm_preset" value="' + pKey + '"'
         + (pChecked ? ' checked' : '') + ' style="margin-right: 4px;">';
    row += pName + '</label></td>';

    row += '<td style="padding: 8px 0; vertical-align: top;">';
    row += '<label for="' + id + '" style="font-weight: normal; margin: 0; cursor: pointer; display: block;">';
    row += pHint;
    if (pValues) {
        row += '<br><span class="text-muted">' + pValues + '</span>';
    }
    row += '</label></td></tr>';

    return row;
}

function openLlmParamDialog() {
    var current = findLlmPreset(gLlmParams.num_ctx, gLlmParams.timeout, gLlmParams.think);

    // ダイアログのHTMLはここで組み立てる。隠し要素を複製する方式にすると
    // 同じidの要素が2つ存在し、$('#...') が画面側の複製を掴んでしまう。
    var html = '<div style="text-align: left;">';
    html += '<label style="display:block;">実行プリセット</label>';

    // プルダウンではなくラジオにして、名前と説明を同時に読めるようにする。
    // 選択の基準が「症状」なので、説明文が見えないと選べない。
    //
    // 名前を1列目、説明と値を2列目に置く表組みにしている。縦に積むと
    // 6項目でダイアログが伸びすぎるため、行数を抑えつつ本文と同じ
    // 文字サイズを保つ。
    html += '<table style="width:100%; margin-bottom: 4px;">';

    for (var i = 0; i < gLlmPresets.length; i++) {
        var p = gLlmPresets[i];
        html += sub490_presetRow(
            p.key, p.name, p.hint,
            'num_ctx ' + p.num_ctx + ' / ' + p.timeout + '秒 / thinking ' + (p.think ? 'ON' : 'なし'),
            current && current.key === p.key
        );
    }

    html += sub490_presetRow(
        LLM_MANUAL_KEY, (gLlmPresets.length + 1) + '. ' + LLM_MANUAL_NAME,
        '値を直接指定します', '', !current
    );

    html += '</table>';

    html += '<hr style="margin: 12px 0;">';
    html += '<label style="display:block;">詳細</label>';

    // コンテキスト長はスライダーと数値入力の両方から決められるようにする。
    // 刻みの良い値はスライダーが速く、プリセットに無い値は数値入力で指定できる
    var ctxOff = !gLlmEngine.supportsNumCtx;
    var disabled = ctxOff ? ' disabled' : '';
    html += '<label style="display:block; font-weight:normal;">コンテキスト長 (num_ctx)</label>';
    html += '<div style="display:flex; align-items:center; gap:10px;">';
    html += '<input type="range" id="dlg_llm_ctx_range" style="flex:1; margin:0;"'
          + ' min="' + LLM_CTX_MIN + '" max="' + LLM_CTX_MAX + '" step="' + LLM_CTX_STEP + '"'
          + ' value="' + sub490_ctxToSlider(gLlmParams.num_ctx) + '"' + disabled + '>';
    html += '<input type="number" id="dlg_llm_ctx" class="form-control" style="width:110px; margin:0;"'
          + ' min="256" step="256" value="' + gLlmParams.num_ctx + '"' + disabled + '>';
    html += '</div>';
    html += '<p class="text-muted" style="margin: 4px 0 12px;">'
          + (ctxOff
             ? gLlmEngine.name + ' では推論エンジン側の設定に従います。'
             : 'スライダーは ' + LLM_CTX_STEP + ' 刻み（' + LLM_CTX_MIN + '〜' + LLM_CTX_MAX + '）。'
               + '細かい値は右の欄に直接入力できます。<br>'
               + '目安: 8192 = レポート1本ぶん / 16384 = thinking あり。'
               + '大きいほど多くの実績を渡せますが、VRAMの使用量が増えます。')
          + '</p>';

    html += '<label style="display:block; font-weight:normal;">タイムアウト (秒)</label>';
    html += '<input type="number" id="dlg_llm_timeout" class="form-control" min="30" step="30" value="' + gLlmParams.timeout + '">';

    var thinkOff = !gLlmEngine.supportsThink;
    html += '<div class="checkbox" style="margin-top: 12px;">';
    html += '<label style="font-weight:normal;"><input type="checkbox" id="dlg_llm_think"'
          + (gLlmParams.think ? ' checked' : '') + (thinkOff ? ' disabled' : '')
          + '> thinking を使う</label>';
    html += '</div>';

    // 強さ。thinking を使うときだけ意味を持つので、チェックに連動して出し入れする。
    // コンテキスト長と同じくスライダーで、左端は「指定しない」（従来どおり ON/OFF だけ送る）
    html += '<div id="dlg_llm_effort_wrap" style="margin: 4px 0 0;">';
    html += '<label style="display:block; font-weight:normal;">thinking の強さ</label>';
    html += '<div style="display:flex; align-items:center; gap:10px;">';
    html += '<input type="range" id="dlg_llm_effort" style="flex:1; margin:0;"'
          + ' min="0" max="' + gLlmThinkEfforts.length + '" step="1"'
          + ' value="' + sub490_effortToIndex(gLlmParams.think_effort) + '">';
    html += '<span id="dlg_llm_effort_label" class="text-muted" style="width:110px;"></span>';
    html += '</div>';
    html += '<p class="text-muted" style="margin: 4px 0 0;">'
          + '強さを持たない銘柄では無視されます。指定しないと従来どおり ON/OFF だけを送ります。'
          + '</p></div>';
    html += '<p class="text-muted" style="margin: 0;">'
          + (thinkOff
             ? gLlmEngine.name + ' では推論エンジン側の設定に従います。'
             : 'thinking はコンテキストを大きく消費します。'
               + '有効にする場合はコンテキスト長に余裕を持たせてください。'
               + '足りないと本文が生成されません。')
          + '</p>';
    html += '</div>';

    Swal.fire({
        title: '実行パラメータ',
        html: html,
        width: 640,
        // Bootstrap3 の html{font-size:10px} により、SweetAlert2 の 1rem 基準が
        // 画面本体(13px)より小さくなる。この画面のCSSで打ち消す
        customClass: { popup: 'gf-llm-param-dialog' },
        showCancelButton: true,
        confirmButtonText: '決定',
        cancelButtonText: 'キャンセル',
        didOpen: function() {
            // セレクタはダイアログ内に限定する
            var $popup = $(Swal.getPopup());

            // プリセットを選んだら詳細欄へ反映する
            $popup.on('change', 'input[name="dlg_llm_preset"]', function() {
                var key = $(this).val();
                if (key === LLM_MANUAL_KEY) {
                    return;   // 手動指定では現在の値をそのまま残す
                }
                for (var i = 0; i < gLlmPresets.length; i++) {
                    if (gLlmPresets[i].key === key) {
                        $popup.find('#dlg_llm_ctx').val(gLlmPresets[i].num_ctx);
                        $popup.find('#dlg_llm_ctx_range').val(sub490_ctxToSlider(gLlmPresets[i].num_ctx));
                        $popup.find('#dlg_llm_timeout').val(gLlmPresets[i].timeout);
                        $popup.find('#dlg_llm_think').prop('checked', gLlmPresets[i].think);
                        return;
                    }
                }
            });

            // スライダーと数値入力を互いに追従させる。数値入力が主で、
            // スライダーは刻みの範囲に収まるときだけ位置を合わせる
            $popup.on('input change', '#dlg_llm_ctx_range', function() {
                $popup.find('#dlg_llm_ctx').val($(this).val()).trigger('change');
            });
            $popup.on('input change', '#dlg_llm_ctx', function() {
                $popup.find('#dlg_llm_ctx_range').val(sub490_ctxToSlider($(this).val()));
            });

            // 強さは thinking を使うときだけ出す。値の表示もここで更新する
            function subEffortSync() {
                var on = $popup.find('#dlg_llm_think').is(':checked') && !thinkOff;
                $popup.find('#dlg_llm_effort_wrap').toggle(on);
                $popup.find('#dlg_llm_effort_label').text(
                    sub490_effortLabel(sub490_indexToEffort($popup.find('#dlg_llm_effort').val())));
            }
            $popup.on('input change', '#dlg_llm_effort, #dlg_llm_think', subEffortSync);
            subEffortSync();

            // 詳細欄を触ったらプリセットの選択を実態に合わせ直す。
            // 選択と値がずれたまま表示されると、どちらが効くのか分からなくなる。
            $popup.on('input change', '#dlg_llm_ctx, #dlg_llm_timeout, #dlg_llm_think', function() {
                var preset = findLlmPreset(
                    parseInt($popup.find('#dlg_llm_ctx').val(), 10),
                    parseInt($popup.find('#dlg_llm_timeout').val(), 10),
                    $popup.find('#dlg_llm_think').is(':checked')
                );
                var key = preset ? preset.key : LLM_MANUAL_KEY;
                $popup.find('input[name="dlg_llm_preset"][value="' + key + '"]').prop('checked', true);
            });
        },
        preConfirm: function() {
            var $popup = $(Swal.getPopup());
            var numCtx = parseInt($popup.find('#dlg_llm_ctx').val(), 10);
            var timeout = parseInt($popup.find('#dlg_llm_timeout').val(), 10);
            var effort = sub490_indexToEffort($popup.find('#dlg_llm_effort').val());

            if (!numCtx || numCtx < 256) {
                Swal.showValidationMessage('コンテキスト長は256以上で指定してください。');
                return false;
            }
            if (!timeout || timeout < 30) {
                Swal.showValidationMessage('タイムアウトは30秒以上で指定してください。');
                return false;
            }
            return {
                num_ctx: numCtx,
                timeout: timeout,
                think: $popup.find('#dlg_llm_think').is(':checked'),
                think_effort: effort
            };
        }
    }).then(function(result) {
        if (!result.isConfirmed) {
            return;
        }
        gLlmParams.num_ctx = result.value.num_ctx;
        gLlmParams.timeout = result.value.timeout;
        gLlmParams.think   = result.value.think;
        gLlmParams.think_effort = result.value.think_effort;
        gLlmCustomized = true;
        updateLlmParamDisplay();
    });
}

function runBatch(batchType) {
    var postData = {
        batch_type: batchType
    };

    var confirmMsg = "";
    if (batchType === 'forecast') {
        // ▼ 追加：プルダウンから日数を取得して postData に格納
        postData.periods = $('#forecast_periods').val();
        confirmMsg = "未来 " + postData.periods + " 日間の来場者予測バッチ(Prophet)を実行しますか？\n(日数が長いほど処理に数秒余分に時間がかかります)";

        // 学習を打ち切る指定。直近の実績を捨てる操作なので、何が起きるかを
        // 明示してから確認する。押した本人が意図していない場合に気づける
        if ($('#forecast_from_ym').is(':checked')) {
            var fromYm = $('#llm_ym').val();
            postData.from_ym = fromYm;

            // 起点が今月より前なら「過去の打ち直し」。評価用の履歴だけを残し、
            // 運用中の最新予測は置き換えない（run_forecast 側の判定と同じ）。
            // どちらになるかで結果の行き先が違うので、押す前に伝える
            var now = new Date();
            var thisYm = now.getFullYear() + '-' + ('0' + (now.getMonth() + 1)).slice(-2);
            var isBackfill = (fromYm < thisYm);

            confirmMsg = "【確認】" + fromYm + " の1日から予測をやり直します。\n\n"
                       + "・学習に使うのは " + fromYm + " の前月末までの実績です\n"
                       + "・それ以降の実績は学習に使いません（予測の精度は通常より落ちます）\n"
                       + "・予測期間 " + postData.periods + " 日は前月末からの日数です。"
                       + "その月の日数に満たない場合は月末まで延ばされます\n";

            if (isBackfill) {
                confirmMsg += "・過去の月なので、最新予測（来場者数情報の画面・ラズパイ同期）は"
                            + "置き換えません。評価用の実行履歴だけを残します\n\n"
                            + "過去の月の精度を評価するための実行です。実行しますか？";
            } else {
                confirmMsg += "・最新予測を置き換えます。来場者数情報の画面とラズパイ同期に反映されます\n\n"
                            + "所見の効果を同じ条件で比べるための実行です。実行しますか？";
            }
        }

    } else if (batchType === 'llm') {
        postData.mode = $('#llm_mode').val();
        postData.ym = $('#llm_ym').val();
        if ($('#llm_model').length > 0) {
            postData.model = $('#llm_model').val();
        }
        // 受け付けない項目は送らない。送っても無視されるだけだが、
        // 画面とサーバで「指定した」認識がずれると調査が難しくなる
        postData.timeout = gLlmParams.timeout;
        if (gLlmEngine.supportsNumCtx) {
            postData.num_ctx = gLlmParams.num_ctx;
        }
        if (gLlmEngine.supportsThink) {
            postData.think = gLlmParams.think ? 'true' : 'false';
            if (gLlmParams.think && gLlmParams.think_effort) {
                postData.think_effort = gLlmParams.think_effort;
            }
        }

        var paramText = [];
        if (gLlmEngine.supportsNumCtx) { paramText.push("num_ctx " + gLlmParams.num_ctx); }
        paramText.push("タイムアウト " + gLlmParams.timeout + "秒");
        if (gLlmEngine.supportsThink) {
            paramText.push("thinking " + (gLlmParams.think ? "ON" : "OFF")
                           + (gLlmParams.think && gLlmParams.think_effort
                              ? " (" + gLlmParams.think_effort + ")" : ""));
        }

        var selectedModeText = $('#llm_mode option:selected').text();
        confirmMsg = postData.ym + " を基準とした [" + selectedModeText + "] レポート生成を実行しますか？\n"
                   + "(" + gLlmEngine.name + " / " + paramText.join(" / ") + ")";

        // レビューは月の合計を前年と比べる。途中の月で実行すると前年の半分の
        // ような表になり、月を間違えて押したことに生成後まで気づけない。
        // 実行前にデータが月末まであるかを問い合わせ、無ければ確認文に添える
        if (postData.mode === 'review') {
            sub490_reviewDataCheck(postData.ym, function(pWarning) {
                sub490_confirmAndRun(batchType, postData, confirmMsg, pWarning);
            });
            return;
        }
    }

    sub490_confirmAndRun(batchType, postData, confirmMsg, '');
}

function sub490_reviewDataCheck(pYm, pCallback) {
    /* 対象月の来場者データが月末まで揃っていなければ、警告文を作って渡す。
       問い合わせに失敗したときは空文で進める。確認の補助であって、
       これが原因で実行できなくなるのは本末転倒 */
    $.ajax({
        type: 'POST',
        url: location.pathname,
        dataType: 'json',
        data: { getMode: 'data_status', ym: pYm },
        beforeSend: function(xhr) { xhr.setRequestHeader('X-CSRFToken', csrftoken); }
    }).done(function(res) {
        if (!res.success || res.complete) {
            pCallback('');
            return;
        }
        var warning;
        if (res.last_day) {
            warning = pYm + " の来場者データは " + sub490_fmtMd(res.last_day)
                    + " までです（月末は " + sub490_fmtMd(res.month_end) + "）。\n"
                    + "途中までのデータで実行しても良いですか？";
        } else {
            warning = pYm + " の来場者データがありません。\n実行しても良いですか？";
        }
        pCallback(warning);
    }).fail(function() {
        pCallback('');
    });
}

function sub490_fmtMd(pYmd) {
    /* '2026-09-14' → '9月14日' */
    var parts = pYmd.split('-');
    return parseInt(parts[1], 10) + '月' + parseInt(parts[2], 10) + '日';
}

function sub490_confirmAndRun(batchType, postData, confirmMsg, pWarning) {
    /* 実行前の確認。他の画面と同じ SweetAlert2 で出す。
       ブラウザ標準の confirm は見た目が揃わないうえ、改行や強調が効かない */
    var html = '<div class="gf_confirm_body">' + sub490_textToHtml(confirmMsg) + '</div>';
    if (pWarning) {
        html = '<div class="gf_confirm_warning">' + sub490_textToHtml(pWarning) + '</div>' + html;
    }

    Swal.fire({
        title: '実行の確認',
        html: html,
        icon: pWarning ? 'warning' : 'question',
        // 幅は文に合わせる。固定幅にすると左寄せの文の右に空白が残る
        width: 'auto',
        customClass: { popup: 'gf-llm-param-dialog gf-llm-confirm-dialog' },
        showCancelButton: true,
        confirmButtonText: '実行する',
        cancelButtonText: 'キャンセル',
        // 途中の月は「実行しない」を既定にする。Enter で通ってしまわないように
        focusCancel: !!pWarning
    }).then(function(r) {
        if (!r.isConfirmed) { return; }
        sub490_startBatch(batchType, postData);
    });
}

function sub490_textToHtml(pText) {
    /* 改行だけを <br> にする。それ以外はエスケープして文字として出す */
    return $('<div>').text(pText).html().replace(/\n/g, '<br>');
}

function sub490_startBatch(batchType, postData) {
    // UIのロックと初期化
    var $console = $('#batch_console');

    // 🌟 修正: JavaScript側で即座に初期ログをフライング表示する（Optimistic UI）
    $console.text("実行開始中...\n");
    if (batchType === 'forecast') {
        $console.append("Prophet 来場者予測バッチを起動しています...\n");
        if (postData.from_ym) {
            $console.append("学習を " + postData.from_ym + " の前月末までに限定します。\n");
        }
    } else if (batchType === 'llm') {
        var modelName = postData.model ? postData.model : "デフォルトモデル";
        $console.append("【" + postData.ym + " / モード: " + postData.mode + "】AIレポートの生成を開始します...\n");
        // 推論エンジンの名前は固定にしない。OpenAI互換を使っていても
        // 「Ollama API」と出ると、どこへ投げているのか読み取れない
        $console.append(gLlmEngine.name + " (モデル: " + modelName + ") にリクエストを送信中...\n");
        $console.append("※AIの応答が完了するまでしばらくお待ちください。\n\n");
    }

    $('button').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    // fetch API を使用してリアルタイムストリーミング受信を行う
    fetch(location.pathname, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrftoken
        },
        body: $.param(postData)
    })
    .then(response => {
        if (!response.ok) throw new Error('ネットワークレスポンスに問題があります。');
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        function readChunks() {
            return reader.read().then(({ done, value }) => {
                if (done) {
                    $('button').prop('disabled', false);
                    if (typeof NProgress != 'undefined') { NProgress.done(); }
                    sub490_afterRun($console.text());
                    return;
                }
                
                // 🌟 修正: 複雑なJSONパースを撤廃し、届いた文字をそのまま追加するだけ！
                const chunkText = decoder.decode(value, { stream: true });
                sub490_appendLog($console, chunkText);
                $console.scrollTop($console[0].scrollHeight);
                
                return readChunks();
            });
        }
        return readChunks();
    })
    .catch(error => {
        $console.append("\n[通信エラー] バッチの実行中にエラーが発生しました。\nError: " + error.message + "\n");
        $('button').prop('disabled', false);
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

// ログに流れる印。まとめを思考なしでやり直したときにバッチが出す
// （report_review_staged.THINK_FALLBACK_MARK と同じ文字列）
var LLM_THINK_FALLBACK_MARK = '[think-fallback]';

function sub490_afterRun(pLogText) {
    /* 処理の終了後に、ログの中では流れて見落とす事柄をダイアログで知らせる。
       thinking なしでのやり直しは、履歴の実行パラメータ（thinking ON）と実際が
       食い違うので、その場で伝える */
    if (pLogText.indexOf(LLM_THINK_FALLBACK_MARK) < 0) { return; }
    // やり直しても本文が出なかったときはバッチの ❌ の説明で足りる
    if (pLogText.indexOf('DBに保存しました') < 0) { return; }

    Swal.fire({
        title: 'まとめは thinking なしで生成しました',
        html: '<div class="gf_confirm_body">'
            + 'thinking が上限に達して本文が生成されなかったため、'
            + 'まとめの段だけ thinking を OFF にしてやり直しました。<br>'
            + '段1〜3の出力はそのまま使っています。レポートは保存されています。<br><br>'
            + '1回目がどこで切れたかは実行ログに出しています。thinking ありで作りたい場合は、'
            + 'Ollama なら実行パラメータの num_ctx を大きく、OpenAI互換なら推論エンジン側の'
            + 'コンテキスト長を広げるか、thinking の短いモデルを選んでください。</div>',
        icon: 'info',
        width: 'auto',
        customClass: { popup: 'gf-llm-param-dialog gf-llm-confirm-dialog' },
        confirmButtonText: '閉じる'
    });
}

function sub490_appendLog($console, pText) {
    /* 実行ログへの追記。'\r'（行頭復帰）は端末と同じく「直前の行を書き直す」
       として扱う。thinking の進捗は数万文字になるので、中身を流す代わりに
       同じ行を書き換えて文字数だけを伸ばしている */
    var parts = pText.split('\r');
    $console.append(parts[0]);

    for (var i = 1; i < parts.length; i++) {
        var current = $console.text();
        var head = current.lastIndexOf('\n');
        $console.text(current.slice(0, head + 1));   // 最後の行を捨てる
        $console.append(parts[i]);
    }
}

function btnPrevMonth() {
    var $dateGroup = $('#llm_ym').closest('.input-group.date');
    // Datepickerから現在設定されている日付を取得
    var currentDate = $dateGroup.datepicker('getDate');
    
    // 万が一取得できない場合は input の value から生成
    if (!currentDate) {
        var val = $('#llm_ym').val();
        if(val) currentDate = new Date(val + '-01');
    }
    
    if (currentDate) {
        // 1ヶ月前にセットしてカレンダーを更新
        currentDate.setMonth(currentDate.getMonth() - 1);
        $dateGroup.datepicker('update', currentDate);
        // イベント任せにせず、ここでも読み直す。ライブラリがどのイベントを
        // 出すかに依存すると、版が変わったときに黙って動かなくなる
        sub490_onYmChanged();
    }
}

function btnNextMonth() {
    var $dateGroup = $('#llm_ym').closest('.input-group.date');
    var currentDate = $dateGroup.datepicker('getDate');
    
    if (!currentDate) {
        var val = $('#llm_ym').val();
        if(val) currentDate = new Date(val + '-01');
    }
    
    if (currentDate) {
        // 1ヶ月後にセットしてカレンダーを更新
        currentDate.setMonth(currentDate.getMonth() + 1);
        $dateGroup.datepicker('update', currentDate);
        // イベント任せにせず、ここでも読み直す。ライブラリがどのイベントを
        // 出すかに依存すると、版が変わったときに黙って動かなくなる
        sub490_onYmChanged();
    }
}


/* ============================================================
   月次所見の状態表示

   入力は 480 で行う。ここでは「入れたつもりで入っていない」まま
   バッチを実行してしまうのを防げれば足りるので、状態だけを出す。
   ============================================================ */

function sub490_remarkStateLoad() {
    var ym = $('#llm_ym').val();
    if (!ym) { return; }
    gLoadedYm = ym;

    $.ajax({
        type: 'POST',
        url: '/480monthly_remark.html',
        dataType: 'json',
        data: { getMode: 'status', ym: ym, cls: 'forecast' },
        beforeSend: function(xhr) {
            if (typeof com_csrftoken !== 'undefined') {
                xhr.setRequestHeader('X-CSRFToken', com_csrftoken);
            }
        }
    }).done(function(res) {
        if (!res.remark_success) { return; }
        $('#remark_state_ym').text('（' + res.ym + '）');
        sub490_remarkStateRow('forecast', res.status.forecast);
        sub490_remarkStateRow('review', res.status.review);
    });
}

function sub490_remarkStateRow(pCls, pState) {
    var label = '未入力';
    var cls = 'gf_rmk_none';

    if (pState.parse_status === 'confirmed') {
        label = '確認済み';
        cls = 'gf_rmk_confirmed';
    } else if (pState.has_text || pState.parse_status === 'parsed') {
        label = (pState.parse_status === 'parsed') ? '未確認' : '未解析';
        cls = 'gf_rmk_parsed';
    }

    $('#remark_state_' + pCls)
        .removeClass('gf_rmk_none gf_rmk_parsed gf_rmk_confirmed')
        .addClass(cls)
        .text(label);

    var detail = [];
    if (pState.event_count) { detail.push(pState.event_count + '件'); }
    if (pState.updated_at)  { detail.push(pState.updated_at); }
    $('#remark_state_' + pCls + '_detail').text(detail.length ? ' ' + detail.join(' / ') : '');
}
