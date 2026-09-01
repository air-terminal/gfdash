/*
    画面名：911attendance_target_config.html
*/

$(document).ready(function() {
    sub911_updateChangedCount();
});

// 「使用しない」の切り替え。チェック時は入力欄を無効化する。
function sub911_onToggleDisable(el) {
    var $chk = $(el);
    var $input = sub911_findInput($chk.data('key'), $chk.data('level'));

    $input.prop('disabled', $chk.is(':checked'));
    if ($chk.is(':checked')) {
        $input.val('');
    }
    sub911_markRow($chk.closest('tr'));
    sub911_updateChangedCount();
}

function sub911_onChange(el) {
    sub911_markRow($(el).closest('tr'));
    sub911_updateChangedCount();
}

function sub911_findInput(key, level) {
    return $('.gf_target_value[data-key="' + key + '"][data-level="' + level + '"]');
}

function sub911_findCheck(key, level) {
    return $('.gf_target_disable[data-key="' + key + '"][data-level="' + level + '"]');
}

// 1行分の入力状態を {key, levels:[v1,v2], changed} で返す（未使用は null）
function sub911_readRow($tr) {
    var key = $tr.data('key');
    var levels = [];
    var changed = false;

    [1, 2].forEach(function(level) {
        var $input = sub911_findInput(key, level);
        var $chk = sub911_findCheck(key, level);

        var disabled = $chk.is(':checked');
        var value = disabled ? null : ($input.val() === '' ? null : parseInt($input.val(), 10));
        levels.push(value);

        var initialDisabled = String($chk.data('initial')) === '1';
        var initialValue = $input.data('initial') === '' ? null : parseInt($input.data('initial'), 10);
        var initial = initialDisabled ? null : initialValue;

        // NaN 同士は比較できないため文字列に寄せて判定する
        if (String(value) !== String(initial)) {
            changed = true;
        }
    });

    return { key: key, levels: levels, changed: changed };
}

function sub911_markRow($tr) {
    $tr.toggleClass('gf_target_changed', sub911_readRow($tr).changed);
}

function sub911_collectChanges() {
    var changes = {};
    $('.gf_target_table tbody tr').each(function() {
        var row = sub911_readRow($(this));
        if (row.changed) {
            changes[row.key] = row.levels;
        }
    });
    return changes;
}

function sub911_updateChangedCount() {
    var count = Object.keys(sub911_collectChanges()).length;
    $('#txt_changed').text(count === 0 ? '' : '変更中: ' + count + '区分');
    $('#btn_save').prop('disabled', count === 0);
}

function sub911_btnReset() {
    $('.gf_target_table tbody tr').each(function() {
        var key = $(this).data('key');
        [1, 2].forEach(function(level) {
            var $input = sub911_findInput(key, level);
            var $chk = sub911_findCheck(key, level);
            var initialDisabled = String($chk.data('initial')) === '1';

            $chk.prop('checked', initialDisabled);
            $input.val($input.data('initial'));
            $input.prop('disabled', initialDisabled);
        });
        $(this).removeClass('gf_target_changed');
    });
    sub911_updateChangedCount();
}

function sub911_btnSave() {
    var changes = sub911_collectChanges();
    var keys = Object.keys(changes);

    if (keys.length === 0) {
        Swal.fire('確認', '変更された項目がありません。', 'info');
        return;
    }

    // 入力欄が空のまま「使用しない」も外れている状態を先に弾く
    var blank = [];
    keys.forEach(function(k) {
        var name = $('tr[data-key="' + k + '"] td:first').text().trim();
        [0, 1].forEach(function(i) {
            var v = changes[k][i];
            var disabled = sub911_findCheck(k, i + 1).is(':checked');
            if (!disabled && (v === null || isNaN(v))) {
                blank.push(name + ' Level' + (i + 1));
            }
        });
    });

    if (blank.length > 0) {
        Swal.fire({
            title: '入力してください',
            html: '次の項目が空欄です。値を入れるか「使用しない」を選んでください。<br><br>'
                + blank.join('<br>'),
            icon: 'warning'
        });
        return;
    }

    sub911_postSave(changes);
}

function sub911_postSave(changes) {
    $('#btn_save').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode: 'save',
            targets: JSON.stringify(changes)
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    }).done(function (res) {
        if (res.save_success) {
            // 保存できた値を新しい初期値として扱う（再読込せずに済ませる）
            Object.keys(changes).forEach(function(k) {
                [1, 2].forEach(function(level) {
                    var $input = sub911_findInput(k, level);
                    var $chk = sub911_findCheck(k, level);
                    $input.data('initial', $input.val());
                    $chk.data('initial', $chk.is(':checked') ? '1' : '0');
                });
                $('tr[data-key="' + k + '"]').removeClass('gf_target_changed');
            });
            sub911_updateChangedCount();
            Swal.fire('保存しました', res.err_message, 'success');
        } else {
            Swal.fire({
                title: '保存できませんでした',
                html: res.err_message,
                icon: 'error'
            });
        }
    }).fail(function () {
        Swal.fire('エラー', '通信に失敗しました。', 'error');
    }).always(function () {
        sub911_updateChangedCount();
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}
