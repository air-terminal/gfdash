/*
    各画面専用javascript
    991ai_data_transfer.html

    書き出しは 905 と同じく fetch で受け取り、ダウンロード指示(attachment)の
    有無で成否を見分ける。取り込みは 990 と同じく Dropzone で /fileupload/ へ
    送り、ファイル名を渡してサーバ側で読む。

    取り込みは必ず「内容を確認」を挟む。既にある月は行ごとのチェックで上書きを
    選ぶ。全期間をまとめて変える操作なので、何がどう変わるかを見てから実行する。
*/

Dropzone.autoDiscover = false;

let myDropzone;
let uploadedFileName = null;
let isBusy = false;
// 確認一覧の行。取り込むときに上書きの指定を組み立てるのに使う
let planRows = [];

$(document).ready(function() {
    sub991_setUploadEnabled(false);

    myDropzone = new Dropzone("#myDropzone", {
        url: "/fileupload/",
        paramName: "file",
        // 1回の取り込みは1ファイル。複数を順に入れると、同じ月がどちらの
        // 内容で残ったかを読み取りにくい
        maxFiles: 1,
        acceptedFiles: ".json",
        addRemoveLinks: true,
        dictDefaultMessage: "ここに書き出したJSONファイルをドラッグ＆ドロップしてください",
        dictRemoveFile: "削除",
        dictMaxFilesExceeded: "ファイルは1つだけです。先に削除してください",

        init: function() {
            var dz = this;
            this.on("sending", function(file, xhr, formData) {
                if (typeof com_csrftoken !== 'undefined') {
                    xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
                }
            });
            this.on("success", function(file, response) {
                uploadedFileName = file.name;
                sub991_clearPlan();
                sub991_setUploadEnabled(true);
            });
            this.on("removedfile", function(file) {
                if (dz.files.length === 0) {
                    uploadedFileName = null;
                    sub991_clearPlan();
                    sub991_setUploadEnabled(false);
                }
            });
            window.clearDropzoneFiles = function() {
                dz.removeAllFiles(true);
            };
        }
    });
});

function sub991_setUploadEnabled(pEnabled) {
    $('#btn_plan').prop('disabled', !pEnabled);
}

function sub991_post(pData) {
    return $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: pData,
        beforeSend: function(xhr) {
            if (typeof com_csrftoken !== 'undefined') {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    });
}

function sub991_escape(pText) {
    return $('<div>').text(pText === undefined || pText === null ? '' : pText).html();
}

// ==========================================
// 書き出し
// ==========================================
function btnExport() {
    var from = $('#export_from').val();
    var to = $('#export_to').val();
    if (from && to && from > to) {
        Swal.fire('確認', '期間の開始が終了より後になっています。', 'warning');
        return;
    }

    $('#btn_export').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    var body = $.param({
        getMode: 'export', fromMonth: from, toMonth: to, remarkCls: $('#export_cls').val()
    });

    fetch(location.pathname, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': com_csrftoken
        },
        body: body
    })
    .then(function(response) {
        if (!response.ok) throw new Error('通信エラーが発生しました。');

        // 成功時も中身は JSON なので、Content-Type では失敗と区別できない。
        // ダウンロード指示の有無で見分ける（905 と同じ）
        var disposition = response.headers.get('Content-Disposition') || '';
        if (disposition.indexOf('attachment') === -1) {
            return response.json().then(function(err) {
                throw new Error(err.err_message || '書き出せませんでした。');
            });
        }

        var filename = 'ai_data.json';
        var matches = /filename="?([^";]+)"?/.exec(disposition);
        if (matches && matches[1]) { filename = matches[1]; }

        return response.blob().then(function(blob) { return { blob: blob, filename: filename }; });
    })
    .then(function(res) {
        var url = window.URL.createObjectURL(res.blob);
        var a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = res.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    })
    .catch(function(error) {
        Swal.fire('書き出し', error.message || '書き出せませんでした。', 'warning');
    })
    .finally(function() {
        $('#btn_export').prop('disabled', false);
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

// ==========================================
// 取り込み: 確認一覧
// ==========================================
function btnPlan() {
    if (!uploadedFileName) {
        Swal.fire('確認', 'ファイルがセットされていません。', 'warning');
        return;
    }
    if (isBusy) { return; }

    isBusy = true;
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    sub991_post({ getMode: 'plan', fileName: uploadedFileName })
    .done(function(res) {
        if (!res.ok) {
            sub991_clearPlan();
            Swal.fire('内容を確認', sub991_escape(res.err_message), 'warning');
            return;
        }
        planRows = res.rows || [];
        sub991_renderPlan(res);
    })
    .fail(function() {
        Swal.fire('エラー', '通信エラーが発生しました。', 'error');
    })
    .always(function() {
        isBusy = false;
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

function sub991_clearPlan() {
    planRows = [];
    $('#plan_table tbody').empty();
    $('#plan_wrap').hide();
}

function sub991_rowKey(pRow) {
    return pRow.target_month + ':' + pRow.remark_cls;
}

function sub991_renderPlan(pRes) {
    var $tbody = $('#plan_table tbody').empty();

    $.each(planRows, function(i, row) {
        var hasError = row.errors.length > 0;
        var check = '';
        // 上書きのチェックは既にある行にだけ出す。新規は追加するだけで、
        // 誤りのある行はどのみち取り込めない
        if (row.exists && !hasError) {
            check = '<input type="checkbox" class="chk_overwrite" data-index="' + i
                  + '" onclick="chkOverwriteRow()">';
        }

        var notes = [];
        $.each(row.errors, function(_, e) {
            notes.push('<div class="text-danger">' + sub991_escape(e) + '</div>');
        });
        if (row.exists && row.has_draft && !hasError) {
            notes.push('<div class="text-warning gf_991_draft_note" style="display: none;">'
                     + '上書きすると、この月の下書きを破棄します。</div>');
        }
        $.each(row.warnings, function(_, w) {
            notes.push('<div class="text-muted">' + sub991_escape(w) + '</div>');
        });

        var status = row.parse_status === 'confirmed' ? '確定' : (row.parse_status === 'none' ? '未確定' : '');
        $tbody.append(
            '<tr data-index="' + i + '">'
          + '<td class="gf_991_check">' + check + '</td>'
          + '<td>' + sub991_escape(row.target_month || '-') + '</td>'
          + '<td>' + sub991_escape(row.remark_cls_name || row.remark_cls || '-')
          + (status ? ' <small class="text-muted">(' + status + ')</small>' : '') + '</td>'
          + '<td class="gf_991_judge_cell"></td>'
          + '<td>' + (row.event_count || 0) + '件</td>'
          + '<td class="gf_991_note">' + notes.join('') + '</td>'
          + '</tr>'
        );
    });

    var existing = planRows.filter(function(r) { return r.exists && r.errors.length === 0; }).length;
    var summary = '書き出し日時: ' + sub991_escape(pRes.exported_at || '-')
                + ' / ' + planRows.length + '件（既にある月 ' + existing + '件）';
    if (pRes.error_count > 0) {
        summary += ' <span class="text-danger"><b>誤り ' + pRes.error_count
                 + '件。直してから取り込んでください。</b></span>';
    }
    $('#plan_summary').html(summary);

    $('#chk_overwrite_all').prop('checked', false).prop('indeterminate', false)
                           .prop('disabled', existing === 0);
    $('#btn_import').prop('disabled', pRes.error_count > 0);
    sub991_refreshJudge();
    $('#plan_wrap').show();
}

// 一括のチェック。既にある行のチェックをまとめて入れる・外す
function chkOverwriteAll(pElem) {
    $('.chk_overwrite').prop('checked', pElem.checked);
    sub991_refreshJudge();
}

function chkOverwriteRow() {
    sub991_refreshJudge();
}

// チェックの状態に合わせて、判定の表示と一括のチェックを更新する
function sub991_refreshJudge() {
    var checks = $('.chk_overwrite');
    var checked = checks.filter(':checked').length;

    // 一部だけ入っているときは中間の表示にする
    $('#chk_overwrite_all').prop('checked', checks.length > 0 && checked === checks.length)
                           .prop('indeterminate', checked > 0 && checked < checks.length);

    $('#plan_table tbody tr').each(function() {
        var row = planRows[$(this).data('index')];
        var judge;
        if (row.errors.length > 0) {
            judge = '<span class="label label-danger gf_991_judge">エラー</span>';
        } else if (!row.exists) {
            judge = '<span class="label label-success gf_991_judge">新規</span>';
        } else if ($(this).find('.chk_overwrite').prop('checked')) {
            judge = '<span class="label label-warning gf_991_judge">上書き</span>';
            $(this).find('.gf_991_draft_note').show();
        } else {
            judge = '<span class="label label-default gf_991_judge">スキップ</span>';
        }
        if (!$(this).find('.chk_overwrite').prop('checked')) {
            $(this).find('.gf_991_draft_note').hide();
        }
        $(this).find('.gf_991_judge_cell').html(judge);
    });
}

// ==========================================
// 取り込み: 実行
// ==========================================
function btnImport() {
    if (isBusy || !uploadedFileName) { return; }

    var overwrite = [];
    $('.chk_overwrite:checked').each(function() {
        overwrite.push(sub991_rowKey(planRows[$(this).data('index')]));
    });
    var created = planRows.filter(function(r) { return !r.exists; }).length;
    var skipped = planRows.filter(function(r) { return r.exists; }).length - overwrite.length;

    if (created === 0 && overwrite.length === 0) {
        Swal.fire('確認', '取り込む行がありません。既にある月を取り込むには、上書きのチェックを入れてください。', 'info');
        return;
    }

    Swal.fire({
        title: '取り込みますか？',
        html: '新規 ' + created + '件 / 上書き ' + overwrite.length + '件 / スキップ ' + skipped + '件',
        icon: overwrite.length > 0 ? 'warning' : 'question',
        showCancelButton: true,
        confirmButtonText: '取り込む',
        cancelButtonText: 'やめる'
    }).then(function(result) {
        if (!result.isConfirmed) { return; }
        sub991_runImport(overwrite);
    });
}

function sub991_runImport(pOverwrite) {
    isBusy = true;
    $('#btn_import').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    sub991_post({ getMode: 'import', fileName: uploadedFileName, overwrite: JSON.stringify(pOverwrite) })
    .done(function(res) {
        if (!res.ok) {
            Swal.fire('取り込み', sub991_escape(res.err_message), 'warning');
            $('#btn_import').prop('disabled', false);
            return;
        }
        var c = res.counts;
        var msg = '新規 ' + c.created + '件 / 上書き ' + c.overwritten + '件 / スキップ ' + c.skipped + '件';
        if (c.drafts_discarded > 0) {
            msg += '<br>破棄した下書き ' + c.drafts_discarded + '件';
        }
        Swal.fire('取り込みが完了しました', msg, 'success');

        // 取り込めたファイルはサーバ側で削除されるため、画面からも外す
        if (typeof clearDropzoneFiles === "function") { clearDropzoneFiles(); }
        uploadedFileName = null;
        sub991_clearPlan();
        sub991_setUploadEnabled(false);
    })
    .fail(function() {
        Swal.fire('エラー', '通信エラーが発生しました。', 'error');
        $('#btn_import').prop('disabled', false);
    })
    .always(function() {
        isBusy = false;
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

function btnCancel() {
    if (isBusy) {
        Swal.fire('処理中です', '完了までお待ちください。', 'info');
        return;
    }
    if (typeof clearDropzoneFiles === "function") { clearDropzoneFiles(); }
    uploadedFileName = null;
    sub991_clearPlan();
    sub991_setUploadEnabled(false);
}
