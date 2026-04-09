/*
    各画面専用javascript
    901weather_upload.html
*/

Dropzone.autoDiscover = false;

// ==============================================================================
// 1. グローバル変数の定義
// ==============================================================================
let myDropzone;
let uploadedFileNames = [];
let isUploading = false;
let successCount = 0;
let errorMessages = [];
let successMessages = []; // ★追加：サーバーからの成功メッセージ保存用
let initialFileCount = 0; // ★追加：処理開始時のファイル数

$(document).ready(function() {
    $('#btn_submit').prop('disabled', true);

    myDropzone = new Dropzone("#myDropzone", {
        url: "/fileupload/", 
        paramName: "file",
        maxFiles: 100,
        acceptedFiles: ".csv",
        addRemoveLinks: true,
        dictDefaultMessage: "ここに複数のCSVファイルをドラッグ＆ドロップしてください",
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

// ==============================================================================
// Uploadボタン押下時の処理
// ==============================================================================
function btnSubmit() {
    if (uploadedFileNames.length === 0) {
        Swal.fire('確認', 'ファイルがセットされていません。', 'warning');
        return;
    }
    if (isUploading) return; 

    // ★追加：最初に何個のファイルをドロップしたかを記憶しておく
    initialFileCount = uploadedFileNames.length;

    isUploading = true;
    $('#btn_submit').prop('disabled', true);
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    processNextFile();
}

// ==============================================================================
// 1ファイルずつDBへ取り込む再帰関数
// ==============================================================================
function processNextFile() {
    if (uploadedFileNames.length === 0) {
        isUploading = false;
        if (typeof NProgress != 'undefined') { NProgress.done(); }
        
        if (errorMessages.length === 0) {
            // ★変更：単独か複数かで表示メッセージを切り替える
            if (initialFileCount === 1) {
                // 単独インポートの場合（サーバーからの詳細件数を表示）
                Swal.fire('インポート成功', successMessages[0], 'success');
            } else {
                // 連続インポートの場合（処理したファイル数を表示）
                Swal.fire('インポート完了', `${successCount}個のファイルのインポートに成功しました！`, 'success');
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
        successMessages = []; // ★追加：リセット
        initialFileCount = 0; // ★追加：リセット
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
        if (res.amedas_update) {
            successCount++; 
            successMessages.push(res.err_message); // ★追加：サーバーからのメッセージを保存
        } else {
            errorMessages.push(`・${targetFileName}: ${res.err_message}`);
        }
    }).fail(function () {
        errorMessages.push(`・${targetFileName}: 通信エラー`);
    }).always(function() {
        processNextFile();
    });
}

// ==============================================================================
// Cancelボタン押下時の処理
// ==============================================================================
function btnCancel() {
    if (isUploading) {
        Swal.fire({
            title: '処理中です',
            text: 'インポート処理をキャンセルしますか？',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
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
    successMessages = []; // ★追加：リセット
    initialFileCount = 0; // ★追加：リセット
    successCount = 0;
    $('#btn_submit').prop('disabled', true);
}