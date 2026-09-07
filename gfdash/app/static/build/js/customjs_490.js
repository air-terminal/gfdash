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

    // 既定値がどのプリセットに当たるかを表示に反映する
    updateLlmParamDisplay();
});

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

function updateLlmParamDisplay() {
    var preset = findLlmPreset(gLlmParams.num_ctx, gLlmParams.timeout, gLlmParams.think);
    $('#llm_param_label').text(preset ? preset.name : LLM_MANUAL_NAME);
    $('#llm_param_ctx').text(gLlmParams.num_ctx);
    $('#llm_param_timeout').text(gLlmParams.timeout);
    $('#llm_param_think').text(gLlmParams.think ? '有効' : '無効');
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
            'num_ctx ' + p.num_ctx + ' / ' + p.timeout + '秒 / 思考' + (p.think ? 'あり' : 'なし'),
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

    html += '<label style="display:block; font-weight:normal;">コンテキスト長 (num_ctx)</label>';
    html += '<input type="number" id="dlg_llm_ctx" class="form-control" min="256" step="256" value="' + gLlmParams.num_ctx + '">';
    html += '<p class="text-muted" style="margin: 4px 0 12px;">大きいほど多くの実績を渡せますが、VRAMの使用量が増えます。</p>';

    html += '<label style="display:block; font-weight:normal;">タイムアウト (秒)</label>';
    html += '<input type="number" id="dlg_llm_timeout" class="form-control" min="30" step="30" value="' + gLlmParams.timeout + '">';

    html += '<div class="checkbox" style="margin-top: 12px;">';
    html += '<label style="font-weight:normal;"><input type="checkbox" id="dlg_llm_think"'
          + (gLlmParams.think ? ' checked' : '') + '> 思考(thinking)を使う</label>';
    html += '</div>';
    html += '<p class="text-muted" style="margin: 0;">思考はコンテキストを大きく消費します。'
          + '有効にする場合はコンテキスト長に余裕を持たせてください。'
          + '足りないと本文が生成されません。</p>';
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
                        $popup.find('#dlg_llm_timeout').val(gLlmPresets[i].timeout);
                        $popup.find('#dlg_llm_think').prop('checked', gLlmPresets[i].think);
                        return;
                    }
                }
            });

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
                think: $popup.find('#dlg_llm_think').is(':checked')
            };
        }
    }).then(function(result) {
        if (!result.isConfirmed) {
            return;
        }
        gLlmParams.num_ctx = result.value.num_ctx;
        gLlmParams.timeout = result.value.timeout;
        gLlmParams.think   = result.value.think;
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
        
    } else if (batchType === 'llm') {
        postData.mode = $('#llm_mode').val();
        postData.ym = $('#llm_ym').val();
        if ($('#llm_model').length > 0) {
            postData.model = $('#llm_model').val();
        }
        postData.num_ctx = gLlmParams.num_ctx;
        postData.timeout = gLlmParams.timeout;
        postData.think   = gLlmParams.think ? 'true' : 'false';

        var selectedModeText = $('#llm_mode option:selected').text();
        confirmMsg = postData.ym + " を基準とした [" + selectedModeText + "] レポート生成を実行しますか？\n"
                   + "(num_ctx " + gLlmParams.num_ctx + " / タイムアウト " + gLlmParams.timeout + "秒"
                   + " / 思考 " + (gLlmParams.think ? "有効" : "無効") + ")";
    }

    if (!confirm(confirmMsg)) {
        return;
    }

    // UIのロックと初期化
    var $console = $('#batch_console');

    // 🌟 修正: JavaScript側で即座に初期ログをフライング表示する（Optimistic UI）
    $console.text("実行開始中...\n");
    if (batchType === 'forecast') {
        $console.append("Prophet 来場者予測バッチを起動しています...\n");
    } else if (batchType === 'llm') {
        var modelName = postData.model ? postData.model : "デフォルトモデル";
        $console.append("【" + postData.ym + " / モード: " + postData.mode + "】AIレポートの生成を開始します...\n");
        $console.append("Ollama API (モデル: " + modelName + ") にリクエストを送信中...\n");
        $console.append("※LLMの思考が完了するまでしばらくお待ちください。\n\n");
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
                    return;
                }
                
                // 🌟 修正: 複雑なJSONパースを撤廃し、届いた文字をそのまま追加するだけ！
                const chunkText = decoder.decode(value, { stream: true });
                $console.append(chunkText);
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
    }
}