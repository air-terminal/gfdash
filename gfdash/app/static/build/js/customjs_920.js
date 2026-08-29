/*
    画面名：920permission_config.html
*/

$(document).ready(function() {
    sub920_updateChangedCount();
});

// 変更された行だけを {テンプレート名: 権限レベル} で集める
function sub920_collectChanges() {
    var changes = {};
    $('.gf_perm_input').each(function() {
        var $sel = $(this);
        var initial = String($sel.data('initial'));
        var current = String($sel.val());
        if (initial !== current) {
            changes[$sel.data('template')] = parseInt(current, 10);
        }
    });
    return changes;
}

function sub920_onChange(el) {
    var $sel = $(el);
    var isChanged = String($sel.data('initial')) !== String($sel.val());
    $sel.closest('tr').toggleClass('gf_perm_changed', isChanged);
    sub920_updateChangedCount();
}

function sub920_updateChangedCount() {
    var count = Object.keys(sub920_collectChanges()).length;
    $('#txt_changed').text(count === 0 ? '' : '変更中: ' + count + '件');
    $('#btn_save').prop('disabled', count === 0);
}

function sub920_btnReset() {
    $('.gf_perm_input').each(function() {
        var $sel = $(this);
        $sel.val(String($sel.data('initial')));
        $sel.closest('tr').removeClass('gf_perm_changed');
    });
    sub920_updateChangedCount();
}

function sub920_btnSave() {
    var changes = sub920_collectChanges();
    var templates = Object.keys(changes);

    if (templates.length === 0) {
        Swal.fire('確認', '変更された項目がありません。', 'info');
        return;
    }

    // 「非表示」は Admin でも開けなくなるため、対象を明示して確認する
    var hiddenNames = [];
    templates.forEach(function(t) {
        if (changes[t] === -1) {
            hiddenNames.push($('tr[data-template="' + t + '"] td:first').text().trim());
        }
    });

    var html = templates.length + '件の権限を変更します。';
    if (hiddenNames.length > 0) {
        html += '<br><br><span style="color:#E74C3C;">次の画面は「非表示」になり、'
              + 'Admin でも開けなくなります。</span><br>'
              + hiddenNames.join('<br>');
    }

    Swal.fire({
        title: '権限を変更しますか？',
        html: html,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '保存',
        cancelButtonText: 'キャンセル'
    }).then((result) => {
        if (result.isConfirmed) {
            sub920_postSave(changes);
        }
    });
}

function sub920_postSave(changes) {
    $('#btn_save').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode: 'save',
            permissions: JSON.stringify(changes)
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    }).done(function (res) {
        if (res.save_success) {
            // 保存できた値を新しい初期値として扱う（再読込せずに済ませる）
            $('.gf_perm_input').each(function() {
                var $sel = $(this);
                if (changes.hasOwnProperty($sel.data('template'))) {
                    $sel.data('initial', $sel.val());
                    $sel.closest('tr').removeClass('gf_perm_changed');
                    // 保存された時点で「未設定」ではなくなる
                    $sel.closest('td').find('[data-role="default-mark"]').remove();
                }
            });
            sub920_updateChangedCount();
            Swal.fire('保存しました', res.err_message, 'success');
        } else {
            Swal.fire('保存できませんでした', res.err_message, 'error');
        }
    }).fail(function () {
        Swal.fire('エラー', '通信に失敗しました。', 'error');
    }).always(function () {
        sub920_updateChangedCount();
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}
