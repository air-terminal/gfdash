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

    /* モデルを変えたら測定結果を読み直す。強さが効くかは銘柄ごとに違うので、
       前の銘柄の判定を持ち回ると、効かない銘柄に強さを送ることになる。
       読み直しの中で、選べなくなった強さは捨てられる */
    $('#llm_model').on('change', function() { sub490_reloadCapability(); });

    // 月次所見の状態。対象年月を変えたら読み直す。
    //
    // イベントは component 要素(.input-group.date)側で拾う。
    // datepicker('update', date) は changeDate を出さず、component 要素に
    // change() を発火する（bootstrap-datepicker の update() の fromArgs 分岐）。
    // input に張ると前月・翌月ボタンで反応しない。input の change はここまで
    // バブルするので、component 要素で見れば全ての経路を拾える。
    $('.input-group.date').on('change changeDate', sub490_onYmChanged);
    sub490_remarkStateLoad();

    /* 読み込み中の表示を終える。custom.js が document.ready で start() するので、
       画面側で done() を呼ばないと出たままになる。

       この画面は他と違い、ロード時にグラフや一覧を読む ajax を持たない。
       他の画面はその ajax の前後で start/done を呼んでおり、その done が
       custom.js 側の start も一緒に終わらせていた。490 には対になる呼び出しが
       無かったため、緑のバーとスピナーが残り続けていた */
    if (typeof NProgress != 'undefined') { NProgress.done(); }
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

// 測定で accepted になった強さだけを選ばせる。
// not accepted の値を選べると、実行が 400 で落ちる
function sub490_availableEfforts() {
    var values = (gLlmCapability && gLlmCapability.effort_values) || [];
    var out = [];
    for (var i = 0; i < gLlmThinkEfforts.length; i++) {
        if (values.indexOf(gLlmThinkEfforts[i]) >= 0) { out.push(gLlmThinkEfforts[i]); }
    }
    return out.length > 0 ? out : gLlmThinkEfforts;
}

// 銘柄が thinking を切り替えられないと測定で分かっているか。
// 未測定のときは true を返さない（測っていないだけの構成で欄を消さない）
function sub490_thinkUnsupported() {
    return !!gLlmCapability && gLlmCapability.measured === true
        && gLlmCapability.think_supported === false;
}

/* 強さ欄を出すか。**「効いた」と実測できた構成でだけ出す。**

   9構成を測って、強さが効いたのは harmony 形式（gpt-oss 系）の1銘柄だけだった。
   Qwen 系は4つのサーバすべてで効かず、gemma4 も効かない。既定で出していると、
   ほとんどの構成で「動かすと何も起こらないスライダー」を見せることになる。

   銘柄名で harmony 系を判定する方法は採らない。表記が揃わない（openai/gpt-oss-20b /
   gpt-oss:20b / *.gguf）うえ、llama.cpp と LM Studio はモデル名を検証しないため、
   .env に書いた名前と動いている銘柄が違っていても分からない。実測を根拠にすれば、
   新しい銘柄が harmony 方式を採ったときも測るだけで使えるようになる。

   未測定と判定できないも畳む。どちらも「効く」と確認できていない */
function sub490_effortAvailable() {
    return !!gLlmCapability && gLlmCapability.measured === true
        && gLlmCapability.effort_status === 'effective';
}

// thinking の強さ。スライダーの 0 は「指定しない」で、1 以降が accepted な強さの順
function sub490_effortToIndex(pValue) {
    var i = sub490_availableEfforts().indexOf(pValue || '');
    return i < 0 ? 0 : i + 1;
}

function sub490_indexToEffort(pIndex) {
    var i = parseInt(pIndex, 10);
    return i > 0 ? (sub490_availableEfforts()[i - 1] || '') : '';
}

function sub490_effortLabel(pValue) {
    return pValue || '指定しない';
}

// 測定結果の説明。利用者が次にどうすればよいか分かる文にする
function sub490_capabilityText() {
    var cap = gLlmCapability || {};
    var when = cap.measured_at ? '（' + cap.measured_at + ' 実測）' : '';
    var text;
    if (!cap.measured) {
        // 強さが銘柄で決まることや、効かない銘柄では無視されることは
        // ここに書かない。この場面で必要なのは「いま指定できない」ことと
        // 「どうすれば指定できるか」の2つだけ
        text = '未測定のため、強さは指定できません。'
             + '強さを指定するにはモデルを測定してください。';
    } else if (sub490_thinkUnsupported()) {
        // 判定（effort_status）より先に見る。切り替えられない銘柄では
        // 強さの効きを測る段まで進んでおらず、判定は未測定のまま残る
        text = 'この銘柄は thinking を切り替えられません' + when + '。'
             + '強さの指定も使えません。';
    } else if (cap.effort_status === 'effective') {
        text = '強さが効きます' + when + '。';
    } else if (cap.effort_status === 'ineffective') {
        // 「送っても無視される」は書かない。欄が無くて指定できない状態なので、
        // 送る話をされても操作する人には意味が通らない
        text = 'この構成では強さの指定が効きません' + when + '。';
    } else if (cap.effort_status === 'indeterminate') {
        // 効くかもしれないが確認できていない。強さは出さない。効いていると
        // 決めて使わせると、ゆらぎを効果と読み違えたまま運用することになる
        // 判定できなかった理由（サーバの出力が毎回変わる）はここに書かない。
        // 測定したときの実行ログと probe_note に残っており、設定を選ぶ場面で
        // 必要な情報ではない
        text = '判定できなかったため、強さは指定できません' + when + '。';
    } else {
        // 測定はしたが判定まで進めなかった（accepted な強さが2つ未満など）。
        // ここで「未測定」と出すと、測った事実が消えて同じ操作を繰り返させる
        text = '測定しましたが、比較できる強さが足りず判定できませんでした' + when + '。';
    }
    if (cap.digest_changed) {
        text += ' 測定したときとモデルの中身が違います。測り直してください。';
    }
    return text;
}

/* 測定を走らせる。生成を伴うので実行ログへ流し、終わったら記録を読み直す。

   4つの値はすべて呼び出し側（ダイアログ）から受け取る。測定は thinking を必ず
   使うが、**記録するのはダイアログにいま入っている値**で、これが「最後に使った
   設定」として保存される。gLlmParams を見ると、ダイアログで変更した内容を
   捨てて古い値を保存してしまう */
function sub490_startProbe(pNumCtx, pTimeout, pThink, pEffort) {
    var $console = $('#batch_console');
    $console.text('thinking の強さの効きを測定します...\n');
    $console.append('※ バリデーション処理とエフェクト検証で計7回の生成を行うため、数分かかります。\n');
    /* 同時に別の生成が走ると、temperature=0 でも出力が変わる。エフェクト検証は
       同じ強さの2回が一致することを前提に判定するので、判定できなくなる。
       実測で確認済み（単独なら一致するサーバで、横から短い要求を入れると分岐した） */
    $console.append('※ 測定中は同じ推論エンジンへ他のリクエストを送らないでください。\n'
                  + '   同時に別の生成が走ると出力が変わり、判定できなくなります。\n\n');

    var postData = {
        getMode: 'probe_think',
        mode: $('#llm_mode').val(),
        num_ctx: pNumCtx,
        timeout: pTimeout,
        think: pThink ? 'true' : 'false',
        think_effort: pEffort || ''
    };
    if ($('#llm_model').length > 0) {
        postData.model = $('#llm_model').val();
    }
    sub490_streamToConsole(postData, function(pLogText) {
        // 成立しなかった場合も読み直す。記録は変わらないが、画面の表示を
        // ログと突き合わせられる状態にしておく
        sub490_reloadCapability(function() {
            /* 測定できなかったときは、その旨のダイアログだけを出す。
               反映するものが無いうえ、SweetAlert2 は重ねられないので、
               完了ダイアログを出すとエラーの表示が差し替わって消える */
            if (sub490_afterProbe(pLogText)) { return; }
            sub490_noticeProbeDone();
        });
    });
}

/* 測定の完了を伝え、OK で実行パラメータを開き直す。

   測定はダイアログを閉じてから走るため、終わったときには設定を変える画面が
   無い。とくに「効いた」と判定された直後は、そこで初めて強さを選べるように
   なる瞬間なので、自分で開き直さないとその状態に辿り着けない。

   自動で開かないのは、測定に数分かかるため。別の作業をしている最中に
   ダイアログが突然開くより、OK を挟むほうが驚きが小さい */
function sub490_noticeProbeDone() {
    var cap = gLlmCapability || {};
    var verdict = cap.status_label
        ? '<div style="margin: 6px 0;"><strong>判定: ' + sub490_escapeHtml(cap.status_label)
          + '</strong></div>'
        : '';
    Swal.fire({
        title: '測定が終了しました',
        html: '<div class="gf_confirm_body">' + verdict
            + '測定結果を反映した実行パラメータを開きます。</div>',
        icon: 'success',
        width: 'auto',
        customClass: { popup: 'gf-llm-param-dialog gf-llm-confirm-dialog' },
        confirmButtonText: 'OK'
    }).then(function(result) {
        // ESC や背景クリックで閉じたときは開かない。閉じる操作をした人に
        // 別のダイアログを出すのは、意図と逆になる
        if (result.isConfirmed) {
            openLlmParamDialog();
        }
    });
}

/* 測定結果を読み直して画面へ反映する。測定はしない。

   pOnDone は読み直しが終わってから呼ぶ。ajax なので、待たずにダイアログを
   組むと測定前の古い記録が表示される */
function sub490_reloadCapability(pOnDone) {
    var postData = { getMode: 'capability' };
    if ($('#llm_model').length > 0) {
        postData.model = $('#llm_model').val();
    }
    $.ajax({
        type: 'POST',
        url: location.pathname,
        dataType: 'json',
        data: postData,
        beforeSend: function(xhr) { xhr.setRequestHeader('X-CSRFToken', csrftoken); }
    }).done(function(res) {
        if (!res || !res.success) { return; }
        gLlmCapability = res;
        // not accepted の強さが選ばれたままだと実行が落ちる。選択肢から外れたら捨てる
        if (gLlmParams.think_effort
            && sub490_availableEfforts().indexOf(gLlmParams.think_effort) < 0) {
            gLlmParams.think_effort = '';
        }
        // 効くと確認できていない構成では強さを持ち回らない。欄を畳むので
        // 画面から取り消せず、指定が残ったまま実行されることになる
        if (!sub490_effortAvailable()) {
            gLlmParams.think_effort = '';
        }
        updateLlmParamDisplay();
    }).always(function() {
        /* 読み直しに失敗しても呼ぶ。呼ばないと再表示の導線が途切れる。
           done より後に登録すること。jQuery は登録順に呼ぶので、先に書くと
           記録を取り込む前に呼ばれ、古い内容でダイアログが組まれる */
        if (pOnDone) { pOnDone(); }
    });
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
        // 前回の設定を復元したときは強さも戻す。num_ctx だけ戻して強さが
        // 残る（あるいは消える）と、前回と同じ条件で回したつもりがずれる
        if (d.restored) {
            gLlmParams.think_effort = d.think_effort || '';
        }
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
    // 復元した値をそのまま使っているときは「モードの既定」ではなく、前回の設定だと出す。
    // 同じ表示だと、.env でもエンジンでもない値が出ている理由が分からない
    var defaultName = (d && d.restored) ? '前回の設定' : 'モードの既定';
    $('#llm_param_label').text(preset ? preset.name : (isDefault ? defaultName : LLM_MANUAL_NAME));
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

    // 前回の設定を復元しているときは、その旨と戻し方を最初に出す。
    // .env でもエンジンの既定でもない値が入っている理由が、これが無いと分からない
    var modeDefaults = sub490_modeDefaults();
    if (modeDefaults && modeDefaults.restored) {
        html += '<p class="text-muted" style="margin: 0 0 10px;">'
              + '前回の設定を復元しています'
              + (modeDefaults.restored_at ? '（' + modeDefaults.restored_at + ' 測定）' : '')
              + '　<button type="button" id="dlg_llm_reset" class="btn btn-default btn-xs">'
              + 'エンジンの既定に戻す</button></p>';
    }

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
    //
    // スライダーは「効いた」と実測できた構成でだけ出す（sub490_effortAvailable）。
    // 選べること自体が「効いているはず」という誤解を生むため、確認できていない
    // 構成では説明と測定ボタンだけを見せる
    html += '<div id="dlg_llm_effort_wrap" style="margin: 4px 0 0;">';
    html += '<label style="display:block; font-weight:normal;">thinking の強さ</label>';
    if (!sub490_effortAvailable()) {
        // スライダーが無いので、説明と測定ボタンだけが残る。左寄せのままだと
        // 行の途中で終わって読みにくいため、ボタンとそろえて中央に置く
        html += '<p class="text-muted" style="margin: 0; text-align: center;">'
              + sub490_capabilityText() + '</p>';
    } else {
        html += '<div style="display:flex; align-items:center; gap:10px;">';
        html += '<input type="range" id="dlg_llm_effort" style="flex:1; margin:0;"'
              + ' min="0" max="' + sub490_availableEfforts().length + '" step="1"'
              + ' value="' + sub490_effortToIndex(gLlmParams.think_effort) + '">';
        html += '<span id="dlg_llm_effort_label" class="text-muted" style="width:110px;"></span>';
        html += '</div>';
        html += '<p class="text-muted" style="margin: 4px 0 0;">'
              + sub490_capabilityText() + '</p>';
    }
    // 測定はこのボタンを押したときだけ走る。生成を伴うため数分かかる。
    // 決定ボタンと同じ btn-primary は使わない。主動作と誤解して押されると、
    // 数分の生成が始まってしまう
    html += '<p style="margin: 6px 0 0; text-align: center;">'
          + '<button type="button" id="dlg_llm_probe" class="btn btn-info btn-sm">'
          + '<i class="fa-solid fa-stopwatch"></i> モデルを測定</button>'
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

            // 測定はダイアログを閉じてから走らせる。数分かかるうえ、進捗は
            // 実行ログに出るので、ダイアログを開いたままにする意味がない。
            // 測るのは今ダイアログに入っている値（これから使う構成）
            // 復元をやめてエンジンの既定へ戻す。値だけ入れ替えて、決定は
            // 利用者に任せる（押した瞬間に確定させない）
            $popup.on('click', '#dlg_llm_reset', function() {
                var base = (modeDefaults && modeDefaults.base) || {};
                if (base.num_ctx) {
                    $popup.find('#dlg_llm_ctx').val(base.num_ctx).trigger('change');
                }
                if (base.timeout) { $popup.find('#dlg_llm_timeout').val(base.timeout); }
                $popup.find('#dlg_llm_think').prop('checked', !!base.think).trigger('change');
                $popup.find('#dlg_llm_effort').val(0).trigger('change');
            });

            $popup.on('click', '#dlg_llm_probe', function() {
                var numCtx = parseInt($popup.find('#dlg_llm_ctx').val(), 10) || gLlmParams.num_ctx;
                var timeout = parseInt($popup.find('#dlg_llm_timeout').val(), 10) || gLlmParams.timeout;
                // thinking と強さもダイアログから読む。gLlmParams（開く前の値）を
                // 使うと、ここで ON にしても false が保存され、次回の復元で
                // thinking が切られる
                var think = $popup.find('#dlg_llm_think').is(':checked');
                var effort = sub490_indexToEffort($popup.find('#dlg_llm_effort').val());

                // 決定ボタンと同じ条件で弾く。測定は保存を伴うので、決定を
                // 通らない値がそのまま「最後に使った設定」になってはいけない
                if (!numCtx || numCtx < 256) {
                    Swal.showValidationMessage('コンテキスト長は256以上で指定してください。');
                    return;
                }
                if (!timeout || timeout < 30) {
                    Swal.showValidationMessage('タイムアウトは30秒以上で指定してください。');
                    return;
                }

                // 測定に使う値を画面にも反映する。保存される値と画面表示が
                // 食い違うと、再読み込みで初めて一致するという動きになる
                gLlmParams.num_ctx = numCtx;
                gLlmParams.timeout = timeout;
                gLlmParams.think = think;
                gLlmParams.think_effort = effort;
                gLlmCustomized = true;
                updateLlmParamDisplay();

                Swal.close();
                sub490_startProbe(numCtx, timeout, think, effort);
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

    sub490_streamToConsole(postData, function(pLogText) { sub490_afterRun(pLogText); });
}

function sub490_streamToConsole(postData, pOnDone) {
    /* POST の応答を実行ログへ流し込む。バッチの実行と強さの測定で共用する。
       どちらも数分かかり、届いた分から読ませたいので同じ仕組みでよい */
    var $console = $('#batch_console');

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
                    if (pOnDone) { pOnDone($console.text()); }
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
        $console.append("\n[通信エラー] 処理中にエラーが発生しました。\nError: " + error.message + "\n");
        $('button').prop('disabled', false);
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

// ログに流れる印。まとめを思考なしでやり直したときにバッチが出す
// （report_review_staged.THINK_FALLBACK_MARK と同じ文字列）
var LLM_THINK_FALLBACK_MARK = '[think-fallback]';

// 測定が成立しなかったときに出る印（view_490ai_batch_run.PROBE_UNMEASURED_MARK）
var LLM_PROBE_UNMEASURED_MARK = '[probe-unmeasured]';

function sub490_afterProbe(pLogText) {
    /* 測定が成立しなかったことをダイアログで知らせる。

       ログに1行出すだけでは足りない。測定は数分かかるので、利用者は流れ終わった
       ログの末尾だけを見る。そこに「記録は残しません」とあっても、接続先や
       モデル名に問題があると気づかないまま「測定できた」と受け取ってしまう。
       記録が残らないので画面の表示も変わらず、失敗が見た目に現れない */
    var at = pLogText.indexOf(LLM_PROBE_UNMEASURED_MARK);
    if (at < 0) { return false; }

    // 印の後ろ、その行の終わりまでが理由
    var rest = pLogText.slice(at + LLM_PROBE_UNMEASURED_MARK.length);
    var end = rest.indexOf('\n');
    var reason = $.trim(end < 0 ? rest : rest.slice(0, end));
    // 強さごとの理由が並ぶと長くなる。全文は実行ログに残っている
    if (reason.length > 200) { reason = reason.slice(0, 200) + '…'; }

    Swal.fire({
        title: '測定できませんでした',
        html: '<div class="gf_confirm_body">'
            + '推論エンジンに問い合わせられなかったため、測定していません。'
            + '<strong>記録は残していません</strong>ので、前回までの内容がそのまま残ります。<br><br>'
            + (reason ? '理由: ' + sub490_escapeHtml(reason) + '<br><br>' : '')
            + '次のどれかを確かめてください。<br>'
            + '・モデル名が推論エンジンにある名前と一致しているか<br>'
            + '・接続先（エンドポイント）が合っているか<br>'
            + '・推論エンジンが起動しているか（起動直後はモデルの読み込み中のことがあります）'
            + '</div>',
        icon: 'error',
        width: 'auto',
        customClass: { popup: 'gf-llm-param-dialog gf-llm-confirm-dialog' },
        confirmButtonText: '閉じる'
    });
    return true;
}

// ダイアログへ埋める前の無害化。理由にはサーバの応答がそのまま入る
function sub490_escapeHtml(pText) {
    return $('<div>').text(pText).html();
}

// バッチが失敗を報告する印。run_llm_analysis が ❌ 付きで stderr へ書く。
// [重大な内部エラー] は view が例外を捕まえたとき
var LLM_RUN_ERROR_MARKS = ['❌', '[重大な内部エラー]'];

/* 実行ログから失敗の説明を取り出す。見つからなければ空文字。

   ❌ の行には対処の案内が続くことがある（タイムアウトの候補、本文が空の
   ときのヒント）ので、空行までをひとまとまりとして扱う */
function sub490_runErrorText(pLogText) {
    var at = -1;
    for (var i = 0; i < LLM_RUN_ERROR_MARKS.length; i++) {
        var found = pLogText.indexOf(LLM_RUN_ERROR_MARKS[i]);
        if (found >= 0 && (at < 0 || found < at)) { at = found; }
    }
    if (at < 0) { return ''; }

    var rest = pLogText.slice(at);
    // 「=== 処理が完了しました ===」は失敗の説明ではないので落とす
    var tail = rest.indexOf('\n=== ');
    if (tail >= 0) { rest = rest.slice(0, tail); }
    var blank = rest.indexOf('\n\n');
    if (blank >= 0) { rest = rest.slice(0, blank); }
    return $.trim(rest);
}

/* 失敗をダイアログで知らせる。

   ログに出るだけだと気づけない。バッチは数分かかるので、利用者は流れ終わった
   末尾だけを見る。そこに ❌ があっても「=== 処理が完了しました ===」で終わって
   いるため、完了したと受け取ってしまう。対応していないモデルを選んだときの
   500 などは、指定を直せば済む話なので、その場で伝えるほうが早い */
function sub490_noticeRunError(pText) {
    Swal.fire({
        title: '処理が失敗しました',
        html: '<div class="gf_confirm_body" style="text-align: left;">'
            + sub490_escapeHtml(pText).replace(/\n/g, '<br>')
            + '</div>',
        icon: 'error',
        width: 'auto',
        customClass: { popup: 'gf-llm-param-dialog gf-llm-confirm-dialog' },
        confirmButtonText: '閉じる'
    });
}

function sub490_afterRun(pLogText) {
    /* 処理の終了後に、ログの中では流れて見落とす事柄をダイアログで知らせる。
       thinking なしでのやり直しは、履歴の実行パラメータ（thinking ON）と実際が
       食い違うので、その場で伝える */

    // 失敗は他の知らせより先に出す。SweetAlert2 は重ねられないため、
    // 後から出すと差し替わって消える
    var error = sub490_runErrorText(pLogText);
    if (error) {
        sub490_noticeRunError(error);
        return;
    }

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
