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
});

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
        var selectedModeText = $('#llm_mode option:selected').text();
        confirmMsg = postData.ym + " を基準とした [" + selectedModeText + "] レポート生成を実行しますか？\n(数十秒〜数分かかる場合があります)";
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