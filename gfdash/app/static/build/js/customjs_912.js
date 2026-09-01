/*
    画面名：912fiscal_period_config.html
*/

// 月ごとの期間プレビュー。テンプレートが json_script で埋め込む。
let sub912_choices = [];

$(document).ready(function() {
    try {
        sub912_choices = JSON.parse($('#month_choices_data').text());
    } catch (e) {
        sub912_choices = [];
    }
    sub912_render();
});

function sub912_getPreview(pMonth) {
    for (var i = 0; i < sub912_choices.length; i++) {
        if (String(sub912_choices[i].month) === String(pMonth)) {
            return sub912_choices[i];
        }
    }
    return null;
}

// 対象月を並べる。期首より前の月は翌年にあたるため色を変える。
function sub912_renderMonths(pMonths, pStartMonth) {
    var html = '';
    var crossed = false;

    for (var i = 0; i < pMonths.length; i++) {
        // 並びが戻ったところから翌年に入る
        if (i > 0 && pMonths[i] < pMonths[i - 1]) {
            crossed = true;
        }
        var cls = 'gf_fiscal_month' + (crossed ? ' gf_fiscal_month_next' : '');
        html += '<span class="' + cls + '">' + pMonths[i] + '月</span>';
    }
    return html;
}

function sub912_render() {
    var month = $('#sel_start_month').val();
    var p = sub912_getPreview(month);
    if (!p) { return; }

    $('#txt_kamiki_label').text(p.kamiki_label);
    $('#txt_simoki_label').text(p.simoki_label);
    $('#txt_kamiki_months').html(sub912_renderMonths(p.kamiki_months, p.month));
    $('#txt_simoki_months').html(sub912_renderMonths(p.simoki_months, p.month));

    if (p.crossing) {
        $('#txt_crossing').text('この設定では ' + p.crossing + ' が年をまたぎます。');
    } else {
        $('#txt_crossing').text('この設定では年をまたぐ期間はありません。');
    }

    var changed = String(month) !== String($('#sel_start_month').data('initial'));
    $('#btn_save').prop('disabled', !changed);
}

function sub912_onChange() {
    sub912_render();
}

function sub912_btnReset() {
    $('#sel_start_month').val($('#sel_start_month').data('initial'));
    sub912_render();
}

function sub912_btnSave() {
    var month = $('#sel_start_month').val();
    var p = sub912_getPreview(month);

    if (String(month) === String($('#sel_start_month').data('initial'))) {
        Swal.fire('確認', '設定は変更されていません。', 'info');
        return;
    }

    Swal.fire({
        title: '年度開始月を変更しますか？',
        html: '<b>' + month + '月</b> 始まりに変更します。<br><br>'
            + p.kamiki_label + '<br>' + p.simoki_label + '<br><br>'
            + '<span style="color:#E74C3C;">対象画面の集計範囲とグラフの並びが変わります。</span>',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '保存',
        cancelButtonText: 'キャンセル'
    }).then((result) => {
        if (result.isConfirmed) {
            sub912_postSave(month);
        }
    });
}

function sub912_postSave(pMonth) {
    $('#btn_save').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode: 'save',
            startMonth: pMonth
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    }).done(function (res) {
        if (res.save_success) {
            $('#sel_start_month').data('initial', pMonth);
            sub912_render();
            Swal.fire('保存しました', res.err_message, 'success');
        } else {
            Swal.fire('保存できませんでした', res.err_message, 'error');
        }
    }).fail(function () {
        Swal.fire('エラー', '通信に失敗しました。', 'error');
    }).always(function () {
        sub912_render();
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}
