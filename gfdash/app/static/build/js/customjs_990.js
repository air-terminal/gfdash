/*
    各画面専用javascript
    990attendance_upload.html

    901 と同じく Dropzone で /fileupload/ へ送り、ファイル名を渡して
    サーバ側で取り込む。901 との違いは「内容を確認」があること。
    取り込む前に件数と注意点を見られると、誤ったファイルをそのまま
    入れてしまう事故が減る。
*/

Dropzone.autoDiscover = false;

let myDropzone;
let uploadedFileNames = [];
let isUploading = false;

$(document).ready(function() {
    sub990_setEnabled(false);

    myDropzone = new Dropzone("#myDropzone", {
        url: "/fileupload/",
        paramName: "file",
        maxFiles: 100,
        acceptedFiles: ".csv",
        addRemoveLinks: true,
        dictDefaultMessage: "ここにCSVファイルをドラッグ＆ドロップしてください",
        dictRemoveFile: "削除",

        init: function() {
            var dz = this;
            this.on("sending", function(file, xhr, formData) {
                if (typeof com_csrftoken !== 'undefined') {
                    xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
                }
            });
            this.on("success", function(file, response) {
                if (!uploadedFileNames.includes(file.name)) {
                    uploadedFileNames.push(file.name);
                }
                sub990_setEnabled(true);
            });
            this.on("removedfile", function(file) {
                uploadedFileNames = uploadedFileNames.filter(name => name !== file.name);
                if (dz.files.length === 0) {
                    sub990_setEnabled(false);
                }
            });
            window.clearDropzoneFiles = function() {
                dz.removeAllFiles(true);
            };
        }
    });
});

function sub990_setEnabled(pEnabled) {
    $('#btn_submit').prop('disabled', !pEnabled);
    $('#btn_check').prop('disabled', !pEnabled);
}

// 内容の確認のみ（DBは更新しない）
function btnCheck() {
    sub990_run('checkonly', '確認結果');
}

// 取り込みの実行
function btnSubmit() {
    sub990_run('filesend', 'インポート結果');
}

function sub990_run(pMode, pTitle) {
    if (uploadedFileNames.length === 0) {
        Swal.fire('確認', 'ファイルがセットされていません。', 'warning');
        return;
    }
    if (isUploading) { return; }

    isUploading = true;
    sub990_setEnabled(false);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    // 取り込みは1ファイルずつ順に行う。同じ日付が複数ファイルに現れた場合、
    // 並行して投げると最後に反映される内容が読めなくなる
    var queue = uploadedFileNames.slice();
    var results = [];

    function next() {
        if (queue.length === 0) {
            isUploading = false;
            if (typeof NProgress != 'undefined') { NProgress.done(); }
            sub990_showResult(pMode, pTitle, results);
            return;
        }

        var fileName = queue.shift();
        $.ajax({
            type: "POST",
            url: location.pathname,
            dataType: 'json',
            data: { getMode: pMode, fileName: fileName },
            beforeSend: function(xhr) {
                if (typeof com_csrftoken !== 'undefined') {
                    xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
                }
            }
        }).done(function(res) {
            results.push({ name: fileName, ok: !!res.attnd_update, msg: res.err_message || '' });
        }).fail(function() {
            results.push({ name: fileName, ok: false, msg: '通信エラー' });
        }).always(next);
    }

    next();
}

function sub990_showResult(pMode, pTitle, pResults) {
    var ng = pResults.filter(function(r) { return !r.ok; });
    var html = pResults.map(function(r) {
        var color = r.ok ? '' : ' style="color:#d33;"';
        return '<div' + color + '><b>' + sub990_escape(r.name) + '</b><br>'
             + sub990_escape(r.msg).replace(/\n/g, '<br>') + '</div>';
    }).join('<hr style="margin:8px 0;">');

    Swal.fire({
        title: pTitle,
        html: '<div style="text-align:left; font-size:13px;">' + html + '</div>',
        icon: ng.length === 0 ? 'success' : 'warning',
        width: 640
    });

    // 取り込めたファイルはサーバ側で削除されるため、一覧からも外す。
    // 確認のみの場合はファイルが残るので、続けて取り込めるようにしておく
    if (pMode === 'filesend' && ng.length === 0) {
        if (typeof clearDropzoneFiles === "function") { clearDropzoneFiles(); }
        uploadedFileNames = [];
        sub990_setEnabled(false);
    } else {
        sub990_setEnabled(true);
    }
}

function sub990_escape(pText) {
    return $('<div>').text(pText === undefined || pText === null ? '' : pText).html();
}

function btnCancel() {
    if (isUploading) {
        Swal.fire('処理中です', '完了までお待ちください。', 'info');
        return;
    }
    if (typeof clearDropzoneFiles === "function") { clearDropzoneFiles(); }
    uploadedFileNames = [];
    sub990_setEnabled(false);
}
