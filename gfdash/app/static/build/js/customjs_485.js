/*
    各画面専用javascript
    485remark_maintenance.html

    登録済みの所見を一覧し、補正の内容(JSON)を直接編集する。
    日常の入力は 480 で行い、こちらは過去分の修正や、画面では表現できない
    編集のための画面。
*/

// 開いている所見のID。一覧を選び直すまで保持する
var gMntId = null;
// 本文の編集へ引き継ぐ対象月と区分
var gMntYm = '';
var gMntCls = '';
// 一覧の全行。絞り込みは画面の中で行う（件数は月に2件ずつしか増えない）
var gMntRows = [];
// 一覧のタブ（所見の区分 'forecast' / 'review'）
var gMntTab = 'forecast';

$(document).ready(function() {
    sub485_loadList();

    // 内容のダイアログは Esc でも閉じる
    $(document).on('keydown', function(ev) {
        if (ev.key === 'Escape' && $('#detail_row').hasClass('gf_mnt_open')
            && !$('.swal2-container').length) {
            btnMntCloseDetail();
        }
    });

    // JSON の欄は中身に合わせて伸ばす。欄の中のスクロールバーを無くし、
    // スクロールをダイアログの1つにする
    if (typeof autosize !== 'undefined') {
        autosize($('#detail_json'));
    }
});

// 予測所見とレビュー所見のタブ（github issue #30）
function btnMntTab(pCls) {
    gMntTab = pCls;
    $('#mnt_tabs > li').each(function() {
        $(this).toggleClass('active', $(this).data('cls') === pCls);
    });
    sub485_applyFilter();
    return false;
}

function btnMntReload() {
    sub485_loadList();
}

function sub485_post(pData, pOnDone) {
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
        if (!res.maint_success) {
            sub485_message('danger', res.err_message, res.detail_errors);
            return;
        }
        pOnDone(res);
    }).fail(function() {
        sub485_message('danger', '通信に失敗しました。');
    }).always(function() {
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

/* ------------------------------------------------------------------
   一覧
   ------------------------------------------------------------------ */

function sub485_loadList() {
    sub485_post({ getMode: 'list' }, function(res) {
        gMntRows = res.rows || [];
        sub485_fillYears(gMntRows);
        sub485_applyFilter();
    });
}

// 期間の選択肢に、所見のある年を新しい順に足す。選んでいた値は保つ
function sub485_fillYears(pRows) {
    var $sel = $('#mnt_f_period');
    var current = $sel.val();
    var years = [];
    for (var i = 0; i < pRows.length; i++) {
        var y = pRows[i].target_month.substring(0, 4);
        if (years.indexOf(y) < 0) { years.push(y); }
    }
    years.sort().reverse();

    var html = '<option value="recent">直近1年</option>';
    for (var j = 0; j < years.length; j++) {
        html += '<option value="' + years[j] + '">' + years[j] + '年</option>';
    }
    html += '<option value="all">すべて</option>';
    $sel.html(html).val(current && $sel.find('option[value="' + current + '"]').length ? current : 'recent');
}

// 絞り込みの条件に合う行だけを一覧に出す（github issue #30）
function sub485_applyFilter() {
    var period = $('#mnt_f_period').val();
    var state = $('#mnt_f_state').val();

    // 直近1年: 今月の11か月前から。翌月以降の所見（先行予測）も含める
    var now = new Date();
    var from = new Date(now.getFullYear(), now.getMonth() - 11, 1);
    var fromYm = from.getFullYear() + '-' + ('0' + (from.getMonth() + 1)).slice(-2);

    // 期間と状態で絞る。区分（タブ）はこの後で分け、タブごとの件数に使う
    var rows = gMntRows.filter(function(r) {
        if (period === 'recent' && r.target_month < fromYm) { return false; }
        if (period !== 'recent' && period !== 'all' && r.target_month.substring(0, 4) !== period) { return false; }
        if (state === 'confirmed' && r.parse_status !== 'confirmed') { return false; }
        if (state === 'unconfirmed' && r.parse_status === 'confirmed') { return false; }
        if (state === 'draft' && !r.has_draft) { return false; }
        return true;
    });

    $('#mnt_tabs > li').each(function() {
        var cls = $(this).data('cls');
        var n = rows.filter(function(r) { return r.remark_cls === cls; }).length;
        $(this).find('.gf_mnt_tab_count').text('（' + n + '件）');
    });

    var tabRows = rows.filter(function(r) { return r.remark_cls === gMntTab; });
    var total = gMntRows.filter(function(r) { return r.remark_cls === gMntTab; }).length;
    $('#mnt_f_count').text(tabRows.length + '件 / 全' + total + '件');
    sub485_renderList(tabRows);
}

function sub485_renderList(pRows) {
    if (!pRows || pRows.length === 0) {
        $('#mnt_tbody').html('<tr><td colspan="5" class="text-muted">'
            + (gMntRows.length ? '条件に合う所見がありません。' : '登録されている所見がありません。')
            + '</td></tr>');
        // 絞り込みで一覧から消えただけなら、開いている内容は閉じない
        if (gMntRows.length === 0) { sub485_closeDetail(); }
        return;
    }

    var html = '';
    for (var i = 0; i < pRows.length; i++) {
        var r = pRows[i];
        html += '<tr data-id="' + r.id + '" onclick="sub485_openDetail(' + r.id + ')">';
        // 1行に収める。区分はタブ、解析モデル・時刻・更新者は内容のダイアログで見る
        html += '<td>' + sub485_escape(r.target_month) + '</td>';
        html += '<td><span class="gf_mnt_state gf_mnt_' + r.parse_status + '">'
              + sub485_escape(r.status_name) + '</span>'
              + (r.has_draft ? '<span class="gf_mnt_state gf_mnt_draft">下書きあり</span>' : '')
              + '</td>';
        html += '<td class="text-right">' + r.event_count + '件</td>';
        html += '<td class="gf_mnt_head" title="' + sub485_escape(r.text_head) + '">'
              + sub485_escape(r.text_head) + '</td>';
        html += '<td>' + sub485_escape((r.updated_at || '').substring(0, 10)) + '</td>';
        html += '</tr>';
    }
    $('#mnt_tbody').html(html);

    // 開いている所見の行に印を付け直す。削除されて全体から消えた場合は閉じる。
    // 絞り込みで一覧から外れただけなら、内容は開いたままにする
    if (gMntId !== null) {
        $('#mnt_tbody tr[data-id="' + gMntId + '"]').addClass('gf_mnt_picked');
        var exists = gMntRows.some(function(r) { return r.id === gMntId; });
        if (!exists) { sub485_closeDetail(); }
    }
}

// 内容のダイアログを閉じる。選んだ行の印は残し、どれを見ていたか分かるようにする
function btnMntCloseDetail() {
    $('#detail_row').removeClass('gf_mnt_open');
    $('body').removeClass('gf_mnt_noscroll');
}

// 選んでいる所見を無くして閉じる（削除などで所見そのものが無くなったとき）
function sub485_closeDetail() {
    gMntId = null;
    $('#mnt_tbody tr').removeClass('gf_mnt_picked');
    btnMntCloseDetail();
}

/* ------------------------------------------------------------------
   詳細
   ------------------------------------------------------------------ */

function sub485_openDetail(pId) {
    sub485_post({ getMode: 'detail', id: pId }, function(res) {
        sub485_renderDetail(res);
        $('#detail_msg').empty();
    });
}

function sub485_renderDetail(pRes) {
    gMntId = pRes.id;
    gMntYm = pRes.target_month;
    gMntCls = pRes.remark_cls;

    $('#mnt_tbody tr').removeClass('gf_mnt_picked');
    $('#mnt_tbody tr[data-id="' + pRes.id + '"]').addClass('gf_mnt_picked');

    // 画面に重ねて開く。開いている間は画面本体をスクロールさせない
    var opening = !$('#detail_row').hasClass('gf_mnt_open');
    $('#detail_row').addClass('gf_mnt_open');
    $('body').addClass('gf_mnt_noscroll');
    // 開き直したときは、スクロールする真ん中の段を先頭に戻す
    if (opening) { $('#detail_scroll').scrollTop(0); }

    // 一覧から外した列（解析モデル・時刻・更新者）は、ここに出す
    var row = null;
    for (var i = 0; i < gMntRows.length; i++) {
        if (gMntRows[i].id === pRes.id) { row = gMntRows[i]; break; }
    }
    $('#detail_meta').text(row
        ? ('解析: ' + (row.parsed_model || '—') + ' / 更新: ' + row.updated_at
           + (row.updated_by ? '（' + row.updated_by + '）' : ''))
        : '');

    $('#detail_header').html(
        sub485_escape(pRes.target_month) + ' ' + sub485_escape(pRes.cls_name)
        + ' <span class="gf_mnt_state gf_mnt_' + pRes.parse_status + '">'
        + sub485_escape(pRes.status_name) + '</span>'
        + (pRes.has_draft ? '<span class="gf_mnt_state gf_mnt_draft">下書きあり</span>' : ''));

    // value ではなく要素へ値として入れる。HTMLとして解釈される余地を残さない
    $('#detail_text').text(pRes.remark_text);
    $('#detail_json').val(pRes.parsed_json);
    // val() で入れただけでは autosize が高さを測り直さない
    if (typeof autosize !== 'undefined') {
        setTimeout(function() { autosize.update($('#detail_json')); }, 0);
    }

    // 編集欄に出ているのが下書きか確定版かを示す。保存は下書きへ書くので、
    // 確定版を見ているつもりで直すと、確定版が変わったと誤解する
    $('#detail_json_kind').text(pRes.has_draft
        ? '― 下書き（確定するまで予測には使われません）'
        : (pRes.parse_status === 'confirmed' ? '― 確定版' : ''));

    // 現在の状態で押せない操作を落とす。押してから気づくことになるため。
    // 確定は、未確定か、確定済みでも下書きがあれば押せる（下書きを確定版へ
    // 写す）。解除は確定済みで下書きが無いときだけ（下書きがあると、確定版を
    // 下書きへ移すときに作業中の下書きを消してしまう）
    var confirmed = (pRes.parse_status === 'confirmed');
    $('#btn_mnt_confirm').prop('disabled', confirmed && !pRes.has_draft);
    $('#btn_mnt_unconfirm').prop('disabled', !confirmed || pRes.has_draft);

    sub485_renderGrounding(pRes.grounding);
}

function sub485_renderGrounding(pGrounding) {
    if (!pGrounding || pGrounding.length === 0) {
        $('#detail_warns').empty();
        return;
    }

    // 指摘は本文から導けない値だけでなく、根拠と係数の食い違い（gitea issue #52）も含む
    var html = '<div class="gf_mnt_warns"><b>要確認の指摘があります</b><ul style="margin:4px 0 0 0; padding-left:18px;">';
    for (var i = 0; i < pGrounding.length; i++) {
        // 承知済みかどうかを添える。同じ見た目で並べると、確認したものまで
        // 未処理に見え、何が残っているのか読み取れない
        var tail = pGrounding[i].ack ? '（確認済み）' : '';
        for (var j = 0; j < pGrounding[i].messages.length; j++) {
            html += '<li>' + (pGrounding[i].index + 1) + '件目: '
                  + sub485_escape(pGrounding[i].messages[j]) + tail + '</li>';
        }
    }
    $('#detail_warns').html(html + '</ul></div>');
}

/* ------------------------------------------------------------------
   操作
   ------------------------------------------------------------------ */

function btnMntEditText() {
    if (gMntId === null) { return; }

    // 対象月と区分を引き継ぐ。遷移先で選び直させると、別の月を開いたまま
    // 編集してしまう事故が起きる
    location.href = '480monthly_remark.html?ym=' + encodeURIComponent(gMntYm)
                  + '&cls=' + encodeURIComponent(gMntCls);
}

function btnMntSaveJson() {
    if (gMntId === null) { return; }

    sub485_post({
        getMode: 'save_json', id: gMntId, parsed_json: $('#detail_json').val()
    }, function(res) {
        sub485_renderDetail(res);
        sub485_message('success', res.message);
        sub485_loadList();
    });
}

function btnMntConfirm() {
    if (gMntId === null) { return; }

    sub485_post({ getMode: 'confirm', id: gMntId }, function(res) {
        sub485_renderDetail(res);
        sub485_message('success', res.message, res.warnings, '注意');
        sub485_loadList();
    });
}

function btnMntUnconfirm() {
    if (gMntId === null) { return; }

    Swal.fire({
        title: '確定を解除しますか？',
        html: '解除すると、この所見は予測とレポートの補正に使われなくなります。',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '解除する',
        cancelButtonText: 'キャンセル',
        customClass: { popup: 'gf-mnt-dialog' }
    }).then(function(r) {
        if (!r.isConfirmed) { return; }

        sub485_post({ getMode: 'unconfirm', id: gMntId }, function(res) {
            sub485_renderDetail(res);
            sub485_message('success', res.message);
            sub485_loadList();
        });
    });
}

function btnMntDelete() {
    if (gMntId === null) { return; }

    Swal.fire({
        title: '所見を削除しますか？',
        html: 'この所見と、そこから作った補正の内容をすべて削除します。',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '削除する',
        cancelButtonText: 'キャンセル',
        customClass: { popup: 'gf-mnt-dialog' }
    }).then(function(r) {
        if (!r.isConfirmed) { return; }

        sub485_post({ getMode: 'delete', id: gMntId }, function(res) {
            sub485_closeDetail();
            sub485_loadList();
            sub485_message('success', res.message);
        });
    });
}

/* ------------------------------------------------------------------
   共通
   ------------------------------------------------------------------ */

function sub485_message(pLevel, pText, pDetails, pDetailTitle) {
    var html = '<div class="alert alert-' + pLevel + '" style="margin: 10px 0 0 0;">'
             + sub485_escape(pText);

    if (pDetails && pDetails.length) {
        html += '<div style="margin-top:6px;"><b>' + (pDetailTitle || '確認してください')
              + '</b><ul style="margin:4px 0 0 0; padding-left:18px;">';
        for (var i = 0; i < pDetails.length; i++) {
            html += '<li>' + sub485_escape(pDetails[i]) + '</li>';
        }
        html += '</ul></div>';
    }

    $('#detail_msg').html(html + '</div>');
}

function sub485_escape(pText) {
    return $('<div>').text(pText === undefined || pText === null ? '' : pText).html();
}
