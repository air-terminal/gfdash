/*
    画面名：905ai_data_sync.html
*/

Dropzone.autoDiscover = false;

let myDropzone;
let uploadedFileNames = [];
let isUploading = false;
let successCount = 0;
let errorMessages = [];
let successMessages = [];
let initialFileCount = 0;

$(document).ready(function() {
    $('#btn_submit').prop('disabled', true);

    myDropzone = new Dropzone("#myDropzone", {
        url: "/fileupload/", 
        paramName: "file",
        maxFiles: 10,
        acceptedFiles: ".json", // ★変更: JSONファイルのみ許可
        addRemoveLinks: true,
        dictDefaultMessage: "ここに同期用JSONファイルをドラッグ＆ドロップしてください",
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
                $('#btn_submit').prop('disabled', false);
            });
            this.on("removedfile", function(file) {
                uploadedFileNames = uploadedFileNames.filter(name => name !== file.name);
                if (dz.files.length === 0) {
                    $('#btn_submit').prop('disabled', true);
                }
            });
            window.clearDropzoneFiles = function() {
                dz.removeAllFiles(true);
            };
        }
    });
});

// ==========================================
// エクスポート処理 (fetchで安全にファイルダウンロード)
// ==========================================
function btnExport() {
    $('#btn_export').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    fetch(location.pathname, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrftoken
        },
        body: 'getMode=export'
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.indexOf('application/json') !== -1) {
            return response.json().then(errData => {
                throw new Error(errData.err_message || 'エクスポートが許可されていません。');
            });
        }
        
        // ファイル名をレスポンスヘッダから取得、無ければ現在時刻から生成
        let filename = `ai_sync_data_${new Date().toISOString().slice(0,10).replace(/-/g,'')}.json`;
        const disposition = response.headers.get('Content-Disposition');
        if (disposition && disposition.indexOf('filename=') !== -1) {
            const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
            const matches = filenameRegex.exec(disposition);
            if (matches != null && matches[1]) {
                filename = matches[1].replace(/['"]/g, '');
            }
        }
        
        return response.blob().then(blob => ({ blob, filename }));
    })
    .then(({ blob, filename }) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        
        $('#btn_export').prop('disabled', false);
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire('エラー', error.message || 'エクスポートに失敗しました。', 'error');
        $('#btn_export').prop('disabled', false);
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

// ==========================================
// インポート処理
// ==========================================
function btnSubmit() {
    if (uploadedFileNames.length === 0) {
        Swal.fire('確認', 'ファイルがセットされていません。', 'warning');
        return;
    }
    if (isUploading) return; 

    initialFileCount = uploadedFileNames.length;
    isUploading = true;
    $('#btn_submit').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    processNextFile();
}

function processNextFile() {
    if (uploadedFileNames.length === 0) {
        isUploading = false;
        if (typeof NProgress != 'undefined') { NProgress.done(); }
        
        if (errorMessages.length === 0) {
            if (initialFileCount === 1) {
                Swal.fire('同期成功', successMessages[0], 'success');
            } else {
                Swal.fire('同期完了', `${successCount}個のファイルの同期に成功しました！`, 'success');
            }
        } else {
            Swal.fire({
                title: '完了（一部エラーあり）',
                html: `成功: ${successCount}件<br><br><span style="color:red;">【エラー内容】</span><br>` + errorMessages.join('<br>'),
                icon: 'warning'
            });
        }
        
        if (typeof clearDropzoneFiles === "function") { clearDropzoneFiles(); }
        successCount = 0;
        errorMessages = [];
        successMessages = []; 
        initialFileCount = 0; 
        $('#btn_submit').prop('disabled', true);
        return;
    }

    let targetFileName = uploadedFileNames.shift();

    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode: 'filesend',
            fileName: targetFileName
        },
        beforeSend: function(xhr, settings) {
            if (typeof com_csrftoken !== 'undefined') {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    }).done(function (res) {
        if (res.sync_success) {
            successCount++; 
            successMessages.push(res.err_message);
        } else {
            errorMessages.push(`・${targetFileName}: ${res.err_message}`);
        }
    }).fail(function () {
        errorMessages.push(`・${targetFileName}: 通信エラー`);
    }).always(function() {
        processNextFile();
    });
}

function btnCancel() {
    if (isUploading) {
        Swal.fire({
            title: '処理中です',
            text: 'インポート処理をキャンセルしますか？',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'はい、中止します',
            cancelButtonText: 'いいえ'
        }).then((result) => {
            if (result.isConfirmed) {
                uploadedFileNames = []; 
                Swal.fire('中止', '残りの処理をキャンセルしました。', 'info');
            }
        });
        return;
    }
    if (typeof clearDropzoneFiles === "function") { clearDropzoneFiles(); }
    uploadedFileNames = [];
    errorMessages = [];
    successMessages = []; 
    initialFileCount = 0; 
    successCount = 0;
    $('#btn_submit').prop('disabled', true);
}