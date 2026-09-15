/*
    各画面専用javascript
    480monthly_remark.html

    月次所見を書き、AIに補正の形へ変換させ、内容を確認して確定する。
    確定したものだけが予測とレポートに使われる。
*/

// 影響の見立ての選択肢。プリセットはサーバ(com_remark.py)が計算した値をそのまま使う。
// 画面で式を持たない理由はテンプレート側のコメントを参照。
var RMK_PCT_KEY = 'percent';      // 率で指定する
var RMK_MANUAL_KEY = 'manual';    // 係数を直接入力する

$(document).ready(function() {
    // 他の画面から対象月と区分を引き継いで開く（485 の「本文を修正」など）。
    // datepicker より先に値を入れる。初期化時に入力欄の値を読むため
    sub480_applyUrlParams();

    if (typeof($.fn.datepicker) !== 'undefined') {
        $('.input-group.date').datepicker({
            language: 'ja',
            minViewMode: 1,
            maxViewMode: 2,
            format: 'yyyy-mm',
            autoclose: true
        });
    }

    // イベントは component 要素(.input-group.date)側で拾う。
    //
    // datepicker('update', date) は changeDate を出さず、component 要素に対して
    // change() を発火する（bootstrap-datepicker の update() の fromArgs 分岐）。
    // input に張ると前月・翌月ボタンで反応せず、changeDate に張ると
    // ボタン経由では発火しない。input の change はここまでバブルするので、
    // component 要素で change を見れば手入力・カレンダー選択・ボタンの
    // すべてを拾える。
    $('.input-group.date').on('change changeDate', sub480_onYmChanged);
    sub480_applyClsView();

    // 本文を編集したら、保存しないと次へ進めないことを示す
    $('#remark_text').on('input', sub480_syncButtons);

    sub480_load();
});

// 直近に読み込んだ対象月。changeDate と change が両方飛ぶ場合に二重で
// 読み込まないようにする
var gLoadedYm = '';

function sub480_applyUrlParams() {
    var params = new URLSearchParams(location.search);

    // 書式を確かめてから入れる。おかしな値を入れるとカレンダーが
    // 初期化に失敗し、画面全体が使えなくなる
    var ym = params.get('ym');
    if (ym && /^\d{4}-\d{2}$/.test(ym)) {
        $('#remark_ym').val(ym);
    }

    var cls = params.get('cls');
    if (cls === 'forecast' || cls === 'review') {
        gRemarkCls = cls;
    }
}

/* ------------------------------------------------------------------
   区分（予測所見 / 振り返り所見）

   予測所見は「保存→解析→確定」で補正の表を持つ。振り返り所見は本文だけで
   「保存→確定」。必要な操作が大きく違うため、タブで別のフォームとして見せ、
   区分ごとに出す要素を切り替える。
   ------------------------------------------------------------------ */

var gRemarkCls = 'forecast';

function btnRemarkSwitchCls(pCls) {
    if (pCls === gRemarkCls) { return false; }
    gRemarkCls = pCls;
    sub480_applyClsView();
    sub480_load();
    return false;   // href="#" で画面の先頭へ飛ばない
}

// 区分に合わせて、タブの選択と要素の表示を切り替える。
// 表示の切り替えはここだけで行い、他の場所で個別に toggle しない
function sub480_applyClsView() {
    var isReview = (gRemarkCls === 'review');

    $('#remark_cls_tabs > li').each(function() {
        $(this).toggleClass('active', $(this).data('cls') === gRemarkCls);
    });
    $('.gf_rmk_intro').each(function() {
        $(this).toggle($(this).data('for') === gRemarkCls);
    });
    $('.gf_rmk_only_forecast').toggle(!isReview);
    $('.gf_rmk_only_review').toggle(isReview);
}

function sub480_onYmChanged() {
    var ym = $('#remark_ym').val();
    if (ym === gLoadedYm) { return; }
    sub480_load();
}

/* ------------------------------------------------------------------
   対象月
   ------------------------------------------------------------------ */

function sub480_moveMonth(pDiff) {
    var $group = $('#remark_ym').closest('.input-group.date');
    var current = $group.datepicker('getDate');

    if (!current) {
        var val = $('#remark_ym').val();
        if (val) { current = new Date(val + '-01'); }
    }
    if (!current) { return; }

    current.setMonth(current.getMonth() + pDiff);
    $group.datepicker('update', current);

    // イベント任せにせず、ここでも読み直す。ライブラリがどのイベントを
    // 出すかに依存すると、版が変わったときに黙って動かなくなる
    sub480_onYmChanged();
}

function btnRemarkPrevMonth() { sub480_moveMonth(-1); }
function btnRemarkNextMonth() { sub480_moveMonth(1); }

function sub480_ym()  { return $('#remark_ym').val(); }
function sub480_cls() { return gRemarkCls; }

/* ------------------------------------------------------------------
   読み書き
   ------------------------------------------------------------------ */

function sub480_post(pData, pOnDone) {
    pData.ym = sub480_ym();
    pData.cls = sub480_cls();

    $.ajax({
        type: 'POST',
        url: location.pathname,
        dataType: 'json',
        data: pData,
        beforeSend: function(xhr) {
            if (typeof com_csrftoken !== 'undefined') {
                xhr.setRequestHeader('X-CSRFToken', com_csrftoken);
            }
            if (typeof NProgress != 'undefined') { NProgress.start(); }
        }
    }).done(function(res) {
        if (!res.remark_success) {
            sub480_message('danger', res.err_message, res.parse_errors);
            return;
        }
        pOnDone(res);
    }).fail(function() {
        sub480_message('danger', '通信に失敗しました。');
    }).always(function() {
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

function sub480_load() {
    gLoadedYm = sub480_ym();

    sub480_post({ getMode: 'get' }, function(res) {
        $('#remark_text').val(res.remark_text);
        sub480_render(res);
        $('#remark_msg').empty();
    });
}

function btnRemarkSave() {
    var text = $('#remark_text').val();

    // 本文を空にして保存した場合も削除とみなす。保存を押せなくすると、
    // 本文を消したあとに進む先が無くなる
    if (text.trim() === '') {
        sub480_confirmDelete();
        return;
    }

    sub480_post({ getMode: 'save', text: text }, function(res) {
        sub480_render(res);
        sub480_message('success', res.message);
    });
}

function btnRemarkDelete() {
    sub480_confirmDelete();
}

function sub480_confirmDelete() {
    Swal.fire({
        title: '所見を削除しますか？',
        html: 'この月の所見と、そこから作った補正の内容をすべて削除します。',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '削除する',
        cancelButtonText: 'キャンセル',
        customClass: { popup: 'gf-rmk-dialog' }
    }).then(function(r) {
        if (!r.isConfirmed) { return; }

        sub480_post({ getMode: 'delete' }, function(res) {
            $('#remark_text').val('');
            sub480_render(res);
            sub480_message('success', res.message);
        });
    });
}

/* ------------------------------------------------------------------
   操作の順序

   保存 → 解析または手で追加 → 確定 の順にしか進めないようにする。
   4つのボタンが常に押せると、どれから押すのか読み取れない。

   順序を強制する実務上の理由もある。解析はサーバに保存済みの本文を
   読むため、編集したまま解析すると前の本文が解析される。
   ------------------------------------------------------------------ */

// サーバに保存されている本文。編集中かどうかの判定に使う
var gSavedText = null;
var gParseStatus = 'none';
// この月・区分の所見が登録されているか。本文が空かどうかでは判断しない
var gExists = false;

function sub480_syncButtons() {
    var text = $('#remark_text').val();
    var saved = (gSavedText !== null);
    var dirty = saved ? (text !== gSavedText) : (text.trim() !== '');
    var eventCount = $('#remark_events_list .gf_ev_card').length;

    // 空にして押したときは削除になる。保存済みの所見がある間は押せるままにする
    var canSave = dirty && (text.trim() !== '' || (gSavedText || '').trim() !== '');
    // 解析と追加は、保存済みの本文に対して行う
    var ready = saved && !dirty && (gSavedText || '').trim() !== '';
    var isReview = (sub480_cls() === 'review');
    // 振り返り所見は本文だけなので、保存できていれば確定できる。
    // 予測所見は補正の内容が要る
    var canConfirm = isReview ? ready
                              : ready && (eventCount > 0 || gParseStatus === 'parsed');

    $('#btn_remark_save').prop('disabled', !canSave);
    // AIが使えない環境では、順序に関わらず解析は押させない
    $('#btn_remark_parse').prop('disabled', !ready || gAiDisabled);
    // 要約は手順の外なので保存状態に依らない。AIが無い環境では押せない。
    // 振り返り所見だけで使える。予測所見の対象月は未来で、備考にあるのは
    // 計画休業程度であり、それは予測が別の経路で既に織り込んでいる
    $('#btn_remark_summary')
        .prop('disabled', gAiDisabled || !isReview)
        .attr('title', isReview
            ? 'その月の日次備考（休業・祝日カレンダーの備考欄）をAIが要約し、本文に挿入します'
            : '日次備考の要約は振り返り所見でのみ使えます');
    $('#btn_remark_add').prop('disabled', !ready);
    $('#btn_remark_confirm, #btn_remark_confirm_text').prop('disabled', !canConfirm);
    // 削除は登録済みの所見がある月でだけ押せる
    $('#btn_remark_delete').prop('disabled', !gExists);

    // ヒントは2枠に出し分ける。所見の枠では本文の操作、補正の枠では表の操作。
    // 1箇所にまとめると、どちらの枠の話をしているのか分からない
    var hint = '';
    if (canSave && text.trim() === '') {
        hint = '「所見を保存」を押すと、この月の所見を削除します。';
    } else if (canSave) {
        hint = 'まず「所見を保存」を押してください。';
    } else if (!ready) {
        hint = isReview ? '所見を入力して保存すると、確定できます。'
                        : '所見を入力して保存すると、解析や追加ができます。';
    } else if (isReview) {
        hint = (gParseStatus === 'confirmed')
             ? '確認済みです。本文を変えた場合はもう一度「確定」を押してください。'
             : '「確定」を押すと、振り返りレポートの材料になります。';
    } else {
        hint = '「AIで解析」を押すと、所見から補正の内容を作ります。';
    }
    $('#remark_hint').text(hint);

    var hint2 = '';
    if (!ready) {
        hint2 = '先に所見を保存してください。';
    } else if (!canConfirm) {
        hint2 = '「手で追加」または上の「AIで解析」で補正の内容を作ってください。';
    } else if (gParseStatus === 'confirmed') {
        hint2 = '確認済みです。内容を変えた場合はもう一度「確定」を押してください。';
    } else {
        hint2 = '内容を確認して「確定」を押すと、予測とレポートに反映されます。';
    }
    $('#remark_hint2').text(hint2);
}

function btnRemarkConfirm() {
    // 振り返り所見は補正を持たない。表が無いので集めても空になるが、
    // 意図を明示するため区分で分ける
    var isReview = (sub480_cls() === 'review');
    var events = isReview ? [] : sub480_collect();

    Swal.fire({
        title: '確定しますか？',
        html: isReview
            ? 'この本文を振り返りレポートの材料として確定します。'
            : '確定すると、' + events.length + '件が予測とレポートの補正に使われます。',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '確定する',
        cancelButtonText: 'キャンセル',
        customClass: { popup: 'gf-rmk-dialog' }
    }).then(function(r) {
        if (!r.isConfirmed) { return; }

        sub480_post({
            getMode: 'events',
            events: JSON.stringify(events),
            confirm: 'true'
        }, function(res) {
            sub480_render(res);
            sub480_message('success', res.message, res.warnings, '注意');
        });
    });
}

/* ------------------------------------------------------------------
   AI解析（ログをストリームで受け取る）
   ------------------------------------------------------------------ */

// ダイアログに溜めたログ。閉じたあと画面下の実行ログへ書き写す
var gParseLog = '';

function btnRemarkParse() {
    if (!$('#remark_text').val().trim()) {
        Swal.fire({ title: '確認', text: '所見が入力されていません。', icon: 'warning',
                    customClass: { popup: 'gf-rmk-dialog' } });
        return;
    }

    gParseLog = '';
    $('#remark_msg').empty();

    // ログはダイアログに出す。画面下の実行ログ欄は補正の内容より下にあり、
    // 実行中に目が届かない。処理が進んでいるかを見せる場所は、操作した
    // 位置の近くに要る
    Swal.fire({
        title: 'AIで解析しています',
        html: '<div style="text-align:left;">'
            + '<p id="dlg_parse_status" class="text-muted">AIに問い合わせています...</p>'
            + '<pre id="dlg_parse_log" class="gf_dlg_log"></pre></div>',
        width: 760,
        // 処理中に閉じられると、進行中かどうか分からなくなる
        allowOutsideClick: false,
        allowEscapeKey: false,
        confirmButtonText: '閉じる',
        customClass: { popup: 'gf-rmk-dialog' },
        didOpen: function() {
            Swal.getConfirmButton().disabled = true;
            sub480_runParse();
        }
    }).then(function() {
        // 閉じたあとに画面下のログへ書き写す。あとから読み返せるようにする
        $('#remark_console').text(gParseLog);
        sub480_parseFinished();
    });
}

function sub480_runParse() {
    var postData = { getMode: 'parse', ym: sub480_ym(), cls: sub480_cls() };
    if ($('#remark_model').length > 0) { postData.model = $('#remark_model').val(); }

    // fetch で少しずつ読む。応答を待ってからまとめて出すと、数分かかる
    // 解析の間なにも起きていないように見える
    fetch(location.pathname, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': (typeof com_csrftoken !== 'undefined') ? com_csrftoken : ''
        },
        body: $.param(postData)
    }).then(function(response) {
        if (!response.ok) { throw new Error('ネットワークの応答に問題があります。'); }

        var reader = response.body.getReader();
        var decoder = new TextDecoder('utf-8');

        function readChunks() {
            return reader.read().then(function(r) {
                if (r.done) {
                    sub480_parseDone('解析が完了しました。');
                    return;
                }
                sub480_appendLog(decoder.decode(r.value, { stream: true }));
                return readChunks();
            });
        }
        return readChunks();
    }).catch(function(error) {
        sub480_appendLog('\n[通信エラー] ' + error.message + '\n');
        sub480_parseDone('通信エラーで中断しました。');
    });
}

function sub480_appendLog(pText) {
    gParseLog += pText;

    var el = document.getElementById('dlg_parse_log');
    if (!el) { return; }
    el.textContent = gParseLog;
    el.scrollTop = el.scrollHeight;
}

function sub480_parseDone(pMessage) {
    $('#dlg_parse_status').text(pMessage);

    var $btn = Swal.getConfirmButton();
    if ($btn) { $btn.disabled = false; }
}

/* ------------------------------------------------------------------
   日次備考の要約（所見の下書き）

   月末に備考を読み返して書き起こす手間と読み落としを減らす。要約は
   textarea へ挿入するだけで保存しない。人が読んで直してから保存する。
   ------------------------------------------------------------------ */

// サーバが流すテキストの区切り。前がログ、後が要約の本文
var SUMMARY_MARKER = '<<<SUMMARY>>>';

var gSummaryRaw = '';

function btnRemarkSummary() {
    gSummaryRaw = '';
    $('#remark_msg').empty();

    Swal.fire({
        title: '日次備考から下書きを作ります',
        html: '<div style="text-align:left;">'
            + '<p id="dlg_sum_status" class="text-muted">AIに問い合わせています...</p>'
            + '<pre id="dlg_sum_log" class="gf_dlg_log gf_dlg_log_small"></pre>'
            + '<textarea id="dlg_sum_text" class="form-control gf_dlg_summary"'
            + ' placeholder="要約がここに流れます。挿入前に直せます。"></textarea>'
            + '<p class="text-muted" style="margin: 6px 0 0 0;">'
            + '備考に書かれていない原因や影響が補われていないか、人名が残っていないかを確かめてから挿入してください。'
            + '</p></div>',
        width: 760,
        allowOutsideClick: false,
        allowEscapeKey: false,
        showCancelButton: true,
        confirmButtonText: '本文に挿入',
        cancelButtonText: '閉じる',
        customClass: { popup: 'gf-rmk-dialog' },
        didOpen: function() {
            // 要約が終わるまで挿入させない。途中の文章を入れると、続きが来ない
            Swal.getConfirmButton().disabled = true;
            sub480_runSummary();
        },
        preConfirm: function() {
            return $(Swal.getPopup()).find('#dlg_sum_text').val();
        }
    }).then(function(r) {
        if (!r.isConfirmed) { return; }
        sub480_insertSummary(r.value);
    });
}

function sub480_runSummary() {
    var postData = { getMode: 'summarize', ym: sub480_ym(), cls: sub480_cls() };
    if ($('#remark_model').length > 0) { postData.model = $('#remark_model').val(); }

    fetch(location.pathname, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': (typeof com_csrftoken !== 'undefined') ? com_csrftoken : ''
        },
        body: $.param(postData)
    }).then(function(response) {
        if (!response.ok) { throw new Error('ネットワークの応答に問題があります。'); }

        var reader = response.body.getReader();
        var decoder = new TextDecoder('utf-8');

        function readChunks() {
            return reader.read().then(function(r) {
                if (r.done) {
                    sub480_summaryDone();
                    return;
                }
                gSummaryRaw += decoder.decode(r.value, { stream: true });
                sub480_renderSummary();
                return readChunks();
            });
        }
        return readChunks();
    }).catch(function(error) {
        gSummaryRaw += '\n[通信エラー] ' + error.message + '\n';
        sub480_renderSummary();
        sub480_summaryDone();
    });
}

// 届いた分を、区切りの前後でログと本文に振り分けて描き直す
function sub480_renderSummary() {
    var at = gSummaryRaw.indexOf(SUMMARY_MARKER);
    var log = (at < 0) ? gSummaryRaw : gSummaryRaw.substring(0, at);
    var text = (at < 0) ? '' : gSummaryRaw.substring(at + SUMMARY_MARKER.length).replace(/^\n/, '');

    var logEl = document.getElementById('dlg_sum_log');
    if (logEl) {
        logEl.textContent = log;
        logEl.scrollTop = logEl.scrollHeight;
    }
    var textEl = document.getElementById('dlg_sum_text');
    if (textEl && at >= 0) {
        textEl.value = text;
        textEl.scrollTop = textEl.scrollHeight;
    }
}

function sub480_summaryDone() {
    var ok = (gSummaryRaw.indexOf(SUMMARY_MARKER) >= 0)
          && $('#dlg_sum_text').val().trim() !== '';

    $('#dlg_sum_status').text(ok ? '要約ができました。内容を確かめて「本文に挿入」を押してください。'
                                 : '要約できませんでした。ログを確認してください。');

    var $btn = Swal.getConfirmButton();
    if ($btn) { $btn.disabled = !ok; }
}

// 本文の末尾に足す。上書きしないのは、既に書いた文章を消さないため。
// 保存はしない。挿入しただけでは「未保存の編集」になり、保存ボタンが押せる
function sub480_insertSummary(pText) {
    var text = (pText || '').trim();
    if (!text) { return; }

    var $area = $('#remark_text');
    var current = $area.val();
    $area.val(current.trim() === '' ? text : current.replace(/\s+$/, '') + '\n\n' + text);

    // 手で打ったときと同じ経路で「編集中」にする
    $area.trigger('input');
    $area.focus();

    sub480_message('info', '下書きを本文に挿入しました。内容を確かめて「所見を保存」を押してください。');
}

function sub480_parseFinished() {
    // 保存はサーバ側で終わっているので、表は読み直して反映する
    sub480_post({ getMode: 'get' }, function(res) {
        sub480_render(res);
        sub480_message('info', '解析結果を読み込みました。内容を確認して「確定」を押してください。');
    });
}

/* ------------------------------------------------------------------
   表示
   ------------------------------------------------------------------ */

function sub480_render(pRes) {
    var status = pRes.parse_status;
    var label = { none: '未解析', parsed: '解析済み（未確認）', confirmed: '確認済み' }[status] || status;

    gSavedText = pRes.remark_text;
    gParseStatus = status;
    gExists = !!pRes.exists;

    $('#remark_status_badge')
        .removeClass('gf_rmk_none gf_rmk_parsed gf_rmk_confirmed')
        .addClass('gf_rmk_' + status)
        .text(label);

    var meta = [];
    if (pRes.updated_at) {
        meta.push('更新 ' + pRes.updated_at + (pRes.updated_by ? '（' + pRes.updated_by + '）' : ''));
    }
    if (pRes.parsed_at) {
        meta.push('解析 ' + pRes.parsed_at + (pRes.parsed_model ? '（' + pRes.parsed_model + '）' : ''));
    }
    $('#remark_meta').text(meta.join(' / '));

    sub480_renderEvents(pRes.events || [], pRes.grounding || []);
    sub480_syncButtons();
}

function btnRemarkAddEvent() {
    var events = sub480_collect();
    events.push({
        name: '', type: 'period', start_date: '', end_date: '',
        factor_low: '', factor_mid: '', factor_high: '',
        rationale: '', use_for_forecast: true, use_for_report: true
    });
    sub480_renderEvents(events);
    sub480_syncButtons();

    // 描き直しで指摘が消えるため、付け直す。追加した行だけでなく、
    // 既にあった行の指摘まで消えてしまう
    sub480_groundingLater();
}

function sub480_renderEvents(pEvents, pGrounding) {
    var html = '';

    for (var i = 0; i < pEvents.length; i++) {
        html += sub480_eventCard(pEvents[i], i + 1);
    }

    var $list = $('#remark_events_list');
    $list.html(html);

    $list.off('change', '.rmk_level').on('change', '.rmk_level', function() {
        sub480_applyLevel($(this).closest('.gf_ev_card'));
    });
    $list.off('input change', '.rmk_pct').on('input change', '.rmk_pct', function() {
        sub480_applyLevel($(this).closest('.gf_ev_card'));
    });

    // 指摘の対象になる項目を直したら洗い直す。名前空間を付けて、上の
    // ハンドラを外さないようにする。
    // 日付は changeDate も見る。bootstrap-datepicker はカレンダーから
    // 選んだときに change を出さない経路がある
    $list.off('.grd').on('change.grd changeDate.grd',
                         '.rmk_type, .rmk_start, .rmk_end, .rmk_level,'
                         + ' .rmk_low, .rmk_mid, .rmk_high',
                         function() {
                             // 値が変われば、前の確認はその値に対するものでは
                             // なくなる。承知を持ち越すと、見ていない値まで
                             // 黙って通ってしまう
                             $(this).closest('.gf_ev_card').data('ack', false);
                             sub480_groundingLater();
                         });
    $list.on('input.grd', '.rmk_pct', function() {
        $(this).closest('.gf_ev_card').data('ack', false);
        sub480_groundingLater();
    });

    // 承知の切り替えは値を変えないので、そのまま出し直す
    $list.on('change.grd', '.rmk_ack', function() {
        $(this).closest('.gf_ev_card').data('ack', $(this).is(':checked'));
        sub480_groundingLater();
    });

    // 日付はカレンダーから選ぶ。カードは描き直すたびに作り直されるので、
    // ここで毎回付け直す
    if (typeof($.fn.datepicker) !== 'undefined') {
        $list.find('.rmk_day').datepicker({
            language: 'ja',
            format: 'yyyy-mm-dd',
            todayHighlight: true,
            autoclose: true,
            clearBtn: true      // 終了日は「無し」にできる必要がある
        });
    }

    // 保存済みの値に合わせて、率の入力欄の出し分けと係数の編集可否を整える
    $list.find('.gf_ev_card').each(function() {
        sub480_syncRow($(this));
        sub480_syncRationale($(this));
    });

    sub480_applyGrounding(pGrounding);

    $('#remark_events_wrap').toggle(pEvents.length > 0);
    $('#remark_events_empty').toggle(pEvents.length === 0);
}

/* ------------------------------------------------------------------
   本文から導けない値の指摘

   読み込み時に一度出すだけでは、日付や種別を直して矛盾が無くなっても
   指摘が残る。消えない指摘は確認の役に立たず、無視する癖を付けてしまう。

   判定はサーバに問い合わせる。式を画面へ写すと、片方だけ直された状態を
   招く（係数の計算式で既に同じ危うさを抱えている）。
   ------------------------------------------------------------------ */

var gGroundingTimer = null;

function sub480_applyGrounding(pGrounding) {
    var map = {};
    if (pGrounding) {
        for (var g = 0; g < pGrounding.length; g++) {
            map[pGrounding[g].index] = pGrounding[g];
        }
    }

    $('#remark_events_list .gf_ev_card').each(function(i) {
        sub480_setCardWarnings($(this), map[i]);
    });
}

function sub480_setCardWarnings($pCard, pFinding) {
    var messages = (pFinding && pFinding.messages) || [];
    var has = (messages.length > 0);
    // 承知の状態はカード側を正とする。押した直後はまだサーバへ届いていない
    var ack = !!$pCard.data('ack');
    var html = '';

    for (var i = 0; i < messages.length; i++) {
        html += '<div><i class="fa fa-exclamation-triangle"></i> '
              + sub480_escape(messages[i]) + '</div>';
    }

    // 承知の操作は指摘と同じ枠に置く。指摘を読んだ流れで押せる位置にないと、
    // 何に対する確認なのか分からなくなる
    if (has) {
        html += '<label class="gf_ev_ack">'
              + '<input type="checkbox" class="rmk_ack"' + (ack ? ' checked' : '') + '> '
              + '内容を確認した（所見に根拠は無いが、この見立てでよい）'
              + '</label>';
    }

    $pCard.toggleClass('gf_ev_card_warn', has && !ack);

    // 承知しても目印は残す。消してしまうと、指摘があった行かどうかが
    // 畳んだ状態から読めない
    $pCard.find('.gf_ev_warn_badge')
          .toggleClass('gf_ev_warn_badge_ack', has && ack)
          .html(has && ack ? '<i class="fa fa-check"></i> 確認済み'
                           : '<i class="fa fa-exclamation-triangle"></i> 要確認')
          .toggle(has);

    $pCard.find('.gf_ev_warns')
          .toggleClass('gf_ev_warns_ack', has && ack)
          .html(html)
          .toggle(has);
}

// 入力のたびに問い合わせない。日付は1文字ずつ変わるため、打ち終わるのを待つ
function sub480_groundingLater() {
    if (gGroundingTimer) { clearTimeout(gGroundingTimer); }
    gGroundingTimer = setTimeout(sub480_groundingCheck, 400);
}

function sub480_groundingCheck() {
    gGroundingTimer = null;

    if ($('#remark_events_list .gf_ev_card').length === 0) {
        return;
    }

    // 判定は保存済みの本文に対して行う。編集中の本文を送らないのは、
    // 保存していない文章を根拠に指摘を消してしまわないため
    $.ajax({
        type: 'POST',
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode: 'check',
            ym: sub480_ym(),
            cls: sub480_cls(),
            events: JSON.stringify(sub480_collect())
        },
        beforeSend: function(xhr) {
            if (typeof com_csrftoken !== 'undefined') {
                xhr.setRequestHeader('X-CSRFToken', com_csrftoken);
            }
        }
    }).done(function(res) {
        // 失敗しても画面は止めない。指摘は確定時にもう一度出る
        if (res.remark_success) { sub480_applyGrounding(res.grounding); }
    });
}

// 1イベント分のカード。項目は Bootstrap のグリッドで並べ、狭い画面では
// 各項目が縦に積まれる。表に詰めるとプルダウンや日付が見切れる
function sub480_eventCard(pEvent, pNo) {
    var e = pEvent;
    // 承知したかどうかはカードに持たせる。指摘の枠に置くと、枠が出ていない
    // 間に保存したときに落ちる
    var html = '<div class="gf_ev_card" data-ack="' + (e.ack ? '1' : '') + '">';

    // 指摘の入れ物は常に置き、中身だけを差し替える。カードごと描き直すと
    // 入力中の値と焦点が飛ぶ（指摘は編集のたびに出し入れするため）
    html += '<div class="gf_ev_head">'
          + '<span class="gf_ev_no">' + pNo + '</span>'
          + '<input type="text" class="rmk_name" placeholder="イベント名" value="' + sub480_attr(e.name) + '">'
          + '<span class="gf_ev_warn_badge" style="display:none;">'
          + '<i class="fa fa-exclamation-triangle"></i> 要確認</span>'
          + '<button type="button" class="btn btn-default btn-xs"'
          + ' onclick="sub480_removeCard(this)" title="このイベントを削除">'
          + '<i class="fa fa-trash"></i></button>'
          + '</div>';

    // 本文から導けない値の指摘。AIの出力を鵜呑みにしないよう、カードの
    // 先頭に出す。確定は止めない（推定であって証明ではない）
    html += '<div class="gf_ev_warns" style="display:none;"></div>';

    html += '<div class="gf_ev_body">';

    // 1段目: いつ・どんな種類の出来事か
    html += '<div class="row">';
    html += '<div class="col-md-3 col-sm-6 col-xs-12 gf_ev_field"><label>種別</label>'
          + '<select class="rmk_type">' + sub480_typeOptions(e.type) + '</select></div>';
    html += '<div class="col-md-3 col-sm-6 col-xs-12 gf_ev_field"><label>開始日</label>'
          + '<input type="text" class="rmk_start rmk_day" placeholder="YYYY-MM-DD" value="'
          + sub480_attr(e.start_date) + '" autocomplete="off"></div>';
    html += '<div class="col-md-3 col-sm-6 col-xs-12 gf_ev_field"><label>終了日</label>'
          + '<input type="text" class="rmk_end rmk_day" placeholder="終了期限なし" value="'
          + sub480_attr(e.end_date) + '" autocomplete="off"></div>';
    html += '<div class="col-md-3 col-sm-6 col-xs-12 gf_ev_field gf_ev_use"><label>用途</label>'
          + '<label><input type="checkbox" class="rmk_fc"' + (e.use_for_forecast ? ' checked' : '') + '> 予測</label>'
          + '<label><input type="checkbox" class="rmk_rp"' + (e.use_for_report ? ' checked' : '') + '> レポート</label>'
          + '</div>';
    html += '</div>';

    // 2段目: どれだけ影響するか
    html += '<div class="row">';
    html += '<div class="col-md-4 col-sm-6 col-xs-12 gf_ev_field"><label>影響の見立て</label>'
          + '<select class="rmk_level">' + sub480_levelOptions(e) + '</select>'
          + '<div class="rmk_pct_wrap" style="display:none; margin-top:4px;">'
          + '<input type="number" class="rmk_pct" step="1" placeholder="例 -7（%）" value="'
          + sub480_attr(sub480_percentOf(e)) + '"></div></div>';

    html += '<div class="col-md-4 col-sm-6 col-xs-12 gf_ev_field">'
          + '<label>係数（下限 / 中央 / 上限）</label>'
          + '<div class="gf_ev_factors">'
          + '<input type="text" class="rmk_low"  value="' + sub480_attr(e.factor_low) + '" readonly>'
          + '<input type="text" class="rmk_mid"  value="' + sub480_attr(e.factor_mid) + '" readonly>'
          + '<input type="text" class="rmk_high" value="' + sub480_attr(e.factor_high) + '" readonly>'
          + '</div></div>';

    html += '<div class="col-md-4 col-sm-12 col-xs-12 gf_ev_field"><label>根拠・補足情報</label>'
          + '<input type="hidden" class="rmk_rationale" value="' + sub480_attr(e.rationale) + '">'
          + '<div class="gf_ev_rationale">'
          + '<button type="button" class="btn btn-info btn-xs rmk_rationale_btn"'
          + ' onclick="sub480_openRationale(this)"><i class="fa fa-pencil"></i> 入力</button>'
          + '<span class="rmk_rationale_state"></span>'
          + '</div></div>';
    html += '</div>';

    html += '</div></div>';
    return html;
}

function sub480_removeCard(pButton) {
    $(pButton).closest('.gf_ev_card').remove();

    // 番号を振り直す。削除したあと番号が飛ぶと、何件あるのか読み取れない
    $('#remark_events_list .gf_ev_no').each(function(i) {
        $(this).text(i + 1);
    });

    var left = $('#remark_events_list .gf_ev_card').length;
    $('#remark_events_wrap').toggle(left > 0);
    $('#remark_events_empty').toggle(left === 0);
    sub480_syncButtons();

    // 削除で番号が繰り上がる。指摘は位置で対応させているので付け直す
    sub480_groundingLater();
}

/* ------------------------------------------------------------------
   根拠

   表の中では有無だけを示し、編集は別窓で行う。根拠は半年後に妥当性を
   見直すための文章で、短く切り詰められると役に立たない。
   ------------------------------------------------------------------ */

function sub480_openRationale(pButton) {
    var $cell = $(pButton).closest('td');
    var $input = $cell.find('.rmk_rationale');
    var name = $cell.closest('.gf_ev_card').find('.rmk_name').val() || '(名称なし)';

    Swal.fire({
        title: '補足入力',
        html: '<div style="text-align:left;">'
            + '<p style="margin-bottom:6px;">' + sub480_escape(name) + '</p>'
            + '<p class="text-muted" style="margin-bottom:6px;">'
            + 'なぜその見立てにしたのかを書いてください。'
            + '所見のどの記述を根拠にしたか、過去に似た事例があったかなど。</p>'
            + '<textarea id="dlg_rationale" class="form-control" rows="6"></textarea>'
            + '</div>',
        width: 640,
        showCancelButton: true,
        confirmButtonText: '決定',
        cancelButtonText: 'キャンセル',
        customClass: { popup: 'gf-rmk-dialog' },
        didOpen: function() {
            // value 属性に入れるとHTMLとして解釈される余地が残る。
            // 要素へ値として設定する
            $(Swal.getPopup()).find('#dlg_rationale').val($input.val()).focus();
        },
        preConfirm: function() {
            return $(Swal.getPopup()).find('#dlg_rationale').val();
        }
    }).then(function(r) {
        if (!r.isConfirmed) { return; }
        $input.val(r.value);
        sub480_syncRationale($cell.closest('.gf_ev_card'));
    });
}

function sub480_syncRationale($pRow) {
    var text = $pRow.find('.rmk_rationale').val() || '';
    var $state = $pRow.find('.rmk_rationale_state');

    if (text.trim() === '') {
        // 根拠が無いと確定できない。表を見た時点で分かるようにする
        $state.html('<span style="color:#C0392B;">未入力</span>');
        return;
    }

    var head = text.trim().replace(/\s+/g, ' ');
    if (head.length > 18) { head = head.substring(0, 18) + '…'; }
    $state.html('<span style="color:#4B5F71;" title="'
              + sub480_attr(text) + '">' + sub480_escape(head) + '</span>');
}

/* ------------------------------------------------------------------
   影響の見立て → 係数
   ------------------------------------------------------------------ */

function sub480_levelOptions(pEvent) {
    var selected = sub480_levelOf(pEvent);
    var html = '';

    for (var i = 0; i < gFactorPresets.length; i++) {
        var p = gFactorPresets[i];
        var text = p.name + (p.percent === 0 ? '' : '（' + (p.percent > 0 ? '+' : '') + p.percent + '%）');
        html += '<option value="' + p.key + '"' + (p.key === selected ? ' selected' : '') + '>' + text + '</option>';
    }

    html += '<option value="' + RMK_PCT_KEY + '"' + (selected === RMK_PCT_KEY ? ' selected' : '') + '>% で指定</option>';
    html += '<option value="' + RMK_MANUAL_KEY + '"' + (selected === RMK_MANUAL_KEY ? ' selected' : '') + '>個別指定</option>';
    return html;
}

// 保存済みの係数が、どのプリセットから作られたものかを引き直す
function sub480_levelOf(pEvent) {
    if (pEvent.factor_mid === null || pEvent.factor_mid === undefined || pEvent.factor_mid === '') {
        return 'none';
    }

    for (var i = 0; i < gFactorPresets.length; i++) {
        var p = gFactorPresets[i];
        if (sub480_sameFactors(p, pEvent)) { return p.key; }
    }
    return RMK_MANUAL_KEY;
}

function sub480_percentOf(pEvent) {
    if (pEvent.factor_mid === null || pEvent.factor_mid === undefined || pEvent.factor_mid === '') {
        return '';
    }
    return Math.round((parseFloat(pEvent.factor_mid) - 1) * 1000) / 10;
}

function sub480_sameFactors(pA, pB) {
    return sub480_num(pA.factor_low) === sub480_num(pB.factor_low)
        && sub480_num(pA.factor_mid) === sub480_num(pB.factor_mid)
        && sub480_num(pA.factor_high) === sub480_num(pB.factor_high);
}

function sub480_num(pValue) {
    if (pValue === null || pValue === undefined || pValue === '') { return null; }
    return Math.round(parseFloat(pValue) * 10000) / 10000;
}

function sub480_applyLevel($pRow) {
    var key = $pRow.find('.rmk_level').val();

    if (key === RMK_MANUAL_KEY) {
        sub480_syncRow($pRow);
        return;
    }

    var factors;
    if (key === RMK_PCT_KEY) {
        factors = sub480_factorsFromPercent($pRow.find('.rmk_pct').val());
    } else {
        factors = sub480_presetByKey(key);
    }

    $pRow.find('.rmk_low').val(factors.factor_low === null ? '' : factors.factor_low);
    $pRow.find('.rmk_mid').val(factors.factor_mid === null ? '' : factors.factor_mid);
    $pRow.find('.rmk_high').val(factors.factor_high === null ? '' : factors.factor_high);

    sub480_syncRow($pRow);
}

function sub480_syncRow($pRow) {
    var key = $pRow.find('.rmk_level').val();
    $pRow.find('.rmk_pct_wrap').toggle(key === RMK_PCT_KEY);
    // 個別指定のときだけ係数を直接触れるようにする。プリセットで作った値を
    // 手で書き換えられると、選択と実際の値がずれたまま保存される
    $pRow.find('.rmk_low, .rmk_mid, .rmk_high').prop('readonly', key !== RMK_MANUAL_KEY);
}

function sub480_presetByKey(pKey) {
    for (var i = 0; i < gFactorPresets.length; i++) {
        if (gFactorPresets[i].key === pKey) { return gFactorPresets[i]; }
    }
    return { factor_low: null, factor_mid: null, factor_high: null };
}

// com_remark.com_factors_from_percent と同じ式。片方だけ変えないこと
function sub480_factorsFromPercent(pPercent) {
    var percent = parseFloat(pPercent);
    if (isNaN(percent) || percent === 0) {
        return { factor_low: null, factor_mid: null, factor_high: null };
    }

    var mid = 1 + percent / 100;
    var half = Math.max(0.03, Math.abs(percent) / 100 * 0.5);

    return {
        factor_low: Math.round(Math.max(0.1, mid - half) * 10000) / 10000,
        factor_mid: Math.round(mid * 10000) / 10000,
        factor_high: Math.round(Math.min(3.0, mid + half) * 10000) / 10000
    };
}

/* ------------------------------------------------------------------
   共通
   ------------------------------------------------------------------ */

function sub480_collect() {
    var events = [];

    $('#remark_events_list .gf_ev_card').each(function() {
        var $card = $(this);
        events.push({
            name: $card.find('.rmk_name').val(),
            type: $card.find('.rmk_type').val(),
            start_date: $card.find('.rmk_start').val(),
            end_date: $card.find('.rmk_end').val(),
            factor_low: $card.find('.rmk_low').val(),
            factor_mid: $card.find('.rmk_mid').val(),
            factor_high: $card.find('.rmk_high').val(),
            rationale: $card.find('.rmk_rationale').val(),
            use_for_forecast: $card.find('.rmk_fc').prop('checked'),
            use_for_report: $card.find('.rmk_rp').prop('checked'),
            // 指摘の枠が出ていないときもカード側から拾う
            ack: !!$card.data('ack')
        });
    });

    return events;
}

function sub480_typeOptions(pType) {
    var html = '';
    for (var key in gTypeNames) {
        if (!gTypeNames.hasOwnProperty(key)) { continue; }
        html += '<option value="' + key + '"' + (key === pType ? ' selected' : '') + '>'
             + gTypeNames[key] + '</option>';
    }
    return html;
}

function sub480_message(pLevel, pText, pDetails, pDetailTitle) {
    var html = '<div class="alert alert-' + pLevel + '" style="margin-bottom: 0;">'
             + sub480_escape(pText);

    if (pDetails && pDetails.length) {
        html += '<div style="margin-top:6px;"><b>' + (pDetailTitle || '確認してください')
              + '</b><ul style="margin:4px 0 0 0; padding-left:18px;">';
        for (var i = 0; i < pDetails.length; i++) {
            html += '<li>' + sub480_escape(pDetails[i]) + '</li>';
        }
        html += '</ul></div>';
    }

    $('#remark_msg').html(html + '</div>');
}

function sub480_escape(pText) {
    return $('<div>').text(pText === undefined || pText === null ? '' : pText).html();
}

function sub480_attr(pValue) {
    return sub480_escape(pValue).replace(/"/g, '&quot;');
}
