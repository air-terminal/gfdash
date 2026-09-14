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

$(document).ready(function() {
    sub485_loadList();
});

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
        sub485_renderList(res.rows);
    });
}

function sub485_renderList(pRows) {
    if (!pRows || pRows.length === 0) {
        $('#mnt_tbody').html('<tr><td colspan="7" class="text-muted">'
            + '登録されている所見がありません。</td></tr>');
        $('#detail_row').hide();
        gMntId = null;
        return;
    }

    var html = '';
    for (var i = 0; i < pRows.length; i++) {
        var r = pRows[i];
        html += '<tr data-id="' + r.id + '" onclick="sub485_openDetail(' + r.id + ')">';
        html += '<td>' + sub485_escape(r.target_month) + '</td>';
        html += '<td>' + sub485_escape(r.cls_name) + '</td>';
        html += '<td><span class="gf_mnt_state gf_mnt_' + r.parse_status + '">'
              + sub485_escape(r.status_name) + '</span></td>';
        html += '<td class="text-right">' + r.event_count + '</td>';
        html += '<td>' + sub485_escape(r.text_head) + '</td>';
        html += '<td>' + sub485_escape(r.parsed_model) + '</td>';
        html += '<td>' + sub485_escape(r.updated_at)
              + (r.updated_by ? '<br><span class="text-muted">' + sub485_escape(r.updated_by) + '</span>' : '')
              + '</td>';
        html += '</tr>';
    }
    $('#mnt_tbody').html(html);

    // 開いていた所見が一覧に残っていれば選択を保つ。削除された場合は閉じる
    if (gMntId !== null) {
        if ($('#mnt_tbody tr[data-id="' + gMntId + '"]').length) {
            sub485_openDetail(gMntId);
        } else {
            $('#detail_row').hide();
            gMntId = null;
        }
    }
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

    $('#detail_row').show();
    $('#detail_header').html(
        sub485_escape(pRes.target_month) + ' ' + sub485_escape(pRes.cls_name)
        + ' <span class="gf_mnt_state gf_mnt_' + pRes.parse_status + '">'
        + sub485_escape(pRes.status_name) + '</span>');

    // value ではなく要素へ値として入れる。HTMLとして解釈される余地を残さない
    $('#detail_text').text(pRes.remark_text);
    $('#detail_json').val(pRes.parsed_json);

    // 確定済みなら確定ボタンを、未確定なら解除ボタンを落とす。
    // 現在の状態で押せない操作を残すと、押してから気づくことになる
    var confirmed = (pRes.parse_status === 'confirmed');
    $('#btn_mnt_confirm').prop('disabled', confirmed);
    $('#btn_mnt_unconfirm').prop('disabled', !confirmed);

    sub485_renderGrounding(pRes.grounding);
}

function sub485_renderGrounding(pGrounding) {
    if (!pGrounding || pGrounding.length === 0) {
        $('#detail_warns').empty();
        return;
    }

    var html = '<div class="gf_mnt_warns"><b>本文から導けない値があります</b><ul style="margin:4px 0 0 0; padding-left:18px;">';
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
            gMntId = null;
            $('#detail_row').hide();
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
