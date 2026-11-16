/*
    各画面専用javascript
    991ai_data_transfer.html

    書き出しは 905 と同じく fetch で受け取り、ダウンロード指示(attachment)の
    有無で成否を見分ける。取り込みは 990 と同じく Dropzone で /fileupload/ へ
    送り、ファイル名を渡してサーバ側で読む。

    取り込みは必ず「内容を確認」を挟む。既にある月は行ごとのチェックで上書きを
    選ぶ。全期間をまとめて変える操作なので、何がどう変わるかを見てから実行する。

    段階2（gitea #89）で AI 実行履歴を足した。確認一覧に実行履歴の表と、
    最新のレポート（tz302）の表を出す。最新のレポートは、無い月は埋め、
    ある月はチェックを入れた月だけを置き換える。
*/

Dropzone.autoDiscover = false;

let myDropzone;
let uploadedFileName = null;
let isBusy = false;
// 確認一覧の行。取り込むときに上書きの指定を組み立てるのに使う
let planRows = [];
// 実行履歴と最新のレポートの確認一覧の行（段階2）
let planRuns = [];
let planAdopts = [];

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

    var kinds = [];
    if ($('#export_kind_remarks').prop('checked')) { kinds.push('remarks'); }
    if ($('#export_kind_runs').prop('checked')) { kinds.push('runs'); }
    if (kinds.length === 0) {
        Swal.fire('確認', '書き出すもの（月次所見・AI 実行履歴）を選んでください。', 'warning');
        return;
    }

    $('#btn_export').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    var body = $.param({
        getMode: 'export', fromMonth: from, toMonth: to, remarkCls: $('#export_cls').val(),
        kinds: kinds.join(','), runKind: $('#export_run_kind').val()
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
        planRuns = res.runs || [];
        planAdopts = res.adopts || [];
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
    planRuns = [];
    planAdopts = [];
    $('#plan_table tbody').empty();
    $('#plan_runs_table tbody').empty();
    $('#plan_adopts_table tbody').empty();
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
    var summary = '書き出し日時: ' + sub991_escape(pRes.exported_at || '-');
    if (planRows.length > 0) {
        summary += ' / 所見 ' + planRows.length + '件（既にある月 ' + existing + '件）';
    }
    if (planRuns.length > 0) {
        var imported = planRuns.filter(function(r) { return r.exists && r.errors.length === 0; }).length;
        summary += ' / 実行 ' + planRuns.length + '件（取り込み済み ' + imported + '件）';
    }
    if (pRes.error_count > 0) {
        summary += ' <span class="text-danger"><b>誤り ' + pRes.error_count
                 + '件。直してから取り込んでください。</b></span>';
    }
    $('#plan_summary').html(summary);

    $('#chk_overwrite_all').prop('checked', false).prop('indeterminate', false)
                           .prop('disabled', existing === 0);
    $('#plan_remarks_wrap').toggle(planRows.length > 0);
    $('#btn_import').prop('disabled', pRes.error_count > 0);
    sub991_refreshJudge();
    sub991_renderRuns();
    sub991_renderAdopts();
    $('#plan_wrap').show();
}

// 実行履歴の表（段階2）。判定は 新規 / 取り込み済み / エラー
function sub991_renderRuns() {
    var $tbody = $('#plan_runs_table tbody').empty();
    $('#plan_runs_wrap').toggle(planRuns.length > 0);

    $.each(planRuns, function(i, row) {
        var judge;
        if (row.errors.length > 0) {
            judge = '<span class="label label-danger gf_991_judge">エラー</span>';
        } else if (row.exists) {
            judge = '<span class="label label-default gf_991_judge">取り込み済み</span>';
        } else {
            judge = '<span class="label label-success gf_991_judge">新規</span>';
        }
        var notes = $.map(row.errors, function(e) {
            return '<div class="text-danger">' + sub991_escape(e) + '</div>';
        });
        var model = [row.llm_model, row.prompt_version].filter(function(v) { return v; }).join(' · ');
        var unit = row.run_kind === 'forecast' ? '行' : '本';

        $tbody.append(
            '<tr>'
          + '<td class="gf_991_nowrap">' + sub991_escape(row.run_kind_name || row.run_kind || '-') + '</td>'
          + '<td class="gf_991_nowrap">' + sub991_escape(row.executed_at || '-') + '</td>'
          + '<td class="gf_991_nowrap">' + sub991_escape(row.target_month || '-') + '</td>'
          + '<td>' + sub991_escape(model || '-') + '</td>'
          + '<td class="gf_991_nowrap">' + (row.item_count || 0) + unit + '</td>'
          + '<td>' + judge + '</td>'
          + '<td class="gf_991_note">' + notes.join('') + '</td>'
          + '</tr>'
        );
    });
}

// 最新のレポートの表（段階2）。チェックは今のレポートがあり、内容が違う行にだけ出す
function sub991_renderAdopts() {
    var $tbody = $('#plan_adopts_table tbody').empty();
    $('#plan_adopts_wrap').toggle(planAdopts.length > 0);

    $.each(planAdopts, function(i, row) {
        var check = '';
        if (row.exists && !row.same) {
            check = '<input type="checkbox" class="chk_adopt" data-index="' + i
                  + '" onclick="chkAdoptRow()">';
        }
        var model = [row.llm_model, row.prompt_version].filter(function(v) { return v; }).join(' · ');
        $tbody.append(
            '<tr data-index="' + i + '">'
          + '<td class="gf_991_check">' + check + '</td>'
          + '<td class="gf_991_nowrap">' + sub991_escape(row.target_month) + '</td>'
          + '<td class="gf_991_nowrap">' + sub991_escape(row.report_cls_name) + '</td>'
          + '<td>' + sub991_escape(model || '-')
          + ' <small class="text-muted gf_991_nowrap">' + sub991_escape(row.executed_at) + '</small></td>'
          + '<td class="gf_991_nowrap">' + (row.exists ? (row.same ? 'あり（同じ内容）' : 'あり') : 'なし') + '</td>'
          + '<td class="gf_991_adopt_judge"></td>'
          + '</tr>'
        );
    });

    var checkable = $('.chk_adopt').length;
    $('#chk_adopt_all').prop('checked', false).prop('indeterminate', false).prop('disabled', checkable === 0);
    sub991_refreshAdopt();
}

function chkAdoptAll(pElem) {
    $('.chk_adopt').prop('checked', pElem.checked);
    sub991_refreshAdopt();
}

function chkAdoptRow() {
    sub991_refreshAdopt();
}

// チェックの状態に合わせて、最新のレポートの判定と一括のチェックを更新する
function sub991_refreshAdopt() {
    var checks = $('.chk_adopt');
    var checked = checks.filter(':checked').length;
    $('#chk_adopt_all').prop('checked', checks.length > 0 && checked === checks.length)
                       .prop('indeterminate', checked > 0 && checked < checks.length);

    $('#plan_adopts_table tbody tr').each(function() {
        var row = planAdopts[$(this).data('index')];
        var judge;
        if (!row.exists) {
            judge = '<span class="label label-success gf_991_judge">追加</span>';
        } else if ($(this).find('.chk_adopt').prop('checked')) {
            judge = '<span class="label label-warning gf_991_judge">置き換え</span>';
        } else {
            judge = '<span class="label label-default gf_991_judge">そのまま</span>';
        }
        $(this).find('.gf_991_adopt_judge').html(judge);
    });
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

    var adopt = [];
    $('.chk_adopt:checked').each(function() {
        var row = planAdopts[$(this).data('index')];
        adopt.push(row.target_month + ':' + row.report_cls);
    });
    var runsNew = planRuns.filter(function(r) { return !r.exists; }).length;
    var reportsAdded = planAdopts.filter(function(r) { return !r.exists; }).length;

    if (created === 0 && overwrite.length === 0 && runsNew === 0 && reportsAdded === 0 && adopt.length === 0) {
        Swal.fire('確認', '取り込むものがありません。既にある月を取り込むには、上書き・採用のチェックを入れてください。', 'info');
        return;
    }

    var html = [];
    if (planRows.length > 0) {
        html.push('所見: 新規 ' + created + '件 / 上書き ' + overwrite.length + '件 / スキップ ' + skipped + '件');
    }
    if (planRuns.length > 0) {
        html.push('実行: 新規 ' + runsNew + '件 / 取り込み済み ' + (planRuns.length - runsNew) + '件');
    }
    if (planAdopts.length > 0) {
        html.push('最新のレポート: 追加 ' + reportsAdded + '件 / 置き換え ' + adopt.length + '件');
    }

    Swal.fire({
        title: '取り込みますか？',
        html: html.join('<br>'),
        icon: (overwrite.length > 0 || adopt.length > 0) ? 'warning' : 'question',
        showCancelButton: true,
        confirmButtonText: '取り込む',
        cancelButtonText: 'やめる'
    }).then(function(result) {
        if (!result.isConfirmed) { return; }
        sub991_runImport(overwrite, adopt);
    });
}

function sub991_runImport(pOverwrite, pAdopt) {
    isBusy = true;
    $('#btn_import').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    sub991_post({ getMode: 'import', fileName: uploadedFileName,
                  overwrite: JSON.stringify(pOverwrite), adopt: JSON.stringify(pAdopt) })
    .done(function(res) {
        if (!res.ok) {
            Swal.fire('取り込み', sub991_escape(res.err_message), 'warning');
            $('#btn_import').prop('disabled', false);
            return;
        }
        var c = res.counts;
        var lines = [];
        if (planRows.length > 0) {
            var line = '所見: 新規 ' + c.created + '件 / 上書き ' + c.overwritten + '件 / スキップ ' + c.skipped + '件';
            if (c.drafts_discarded > 0) {
                line += '（破棄した下書き ' + c.drafts_discarded + '件）';
            }
            lines.push(line);
        }
        if (planRuns.length > 0) {
            lines.push('実行: 新規 ' + c.runs_created + '件 / 取り込み済み ' + c.runs_skipped + '件');
            lines.push('最新のレポート: 追加 ' + c.reports_added + '件 / 置き換え ' + c.reports_replaced + '件');
        }
        var msg = lines.join('<br>');
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
