/*
    画面名：910weather_station_config.html
*/

// 保存済みの設定。変更検知と「元に戻す」に使用する
let sub910_initial = {
    precNo: '',
    kansyoBlockNo: '',
    amedasBlockNo: ''
};

$(document).ready(function() {
    sub910_initial.precNo = $('#init_prec_no').val() || '';
    sub910_initial.kansyoBlockNo = $('#init_kansyo_block_no').val() || '';
    sub910_initial.amedasBlockNo = $('#init_amedas_block_no').val() || '';

    sub910_btnReset();
});

// 都府県を選び直したときは地点一覧を入れ替える
function sub910_onChangePrec() {
    var precNo = $('#sel_prec').val();

    if (!precNo) {
        sub910_setStationOptions('#sel_kansyo', [], '');
        sub910_setStationOptions('#sel_amedas', [], '');
        sub910_onChangeStation();
        return;
    }

    // 保存済みの都府県に戻した場合のみ、保存済みの地点を初期選択する
    var isInitialPrec = (precNo === sub910_initial.precNo);
    var selectKansyo = isInitialPrec ? sub910_initial.kansyoBlockNo : '';
    var selectAmedas = isInitialPrec ? sub910_initial.amedasBlockNo : '';

    sub910_loadStations(precNo, selectKansyo, selectAmedas);
}

function sub910_loadStations(precNo, selectKansyo, selectAmedas) {
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode: 'stations',
            precNo: precNo
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    }).done(function (results) {
        sub910_setStationOptions('#sel_kansyo', results.kansyo, selectKansyo);
        sub910_setStationOptions('#sel_amedas', results.amedas, selectAmedas);
        sub910_onChangeStation();
    }).fail(function () {
        Swal.fire('エラー', '観測地点の一覧を取得できませんでした。', 'error');
    }).always(function () {
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

function sub910_setStationOptions(selector, stations, selectBlockNo) {
    var $sel = $(selector);
    $sel.empty();

    if (!stations || stations.length === 0) {
        $sel.append($('<option>').val('').text('-- 都府県を選択してください --'));
        $sel.prop('disabled', true);
        return;
    }

    $sel.append($('<option>').val('').text('-- 選択してください --'));
    $.each(stations, function(_, s) {
        // アメダス欄には気象官署も並ぶため、どちらなのかが分かるようにする
        var label = (s.station_type === 's')
            ? (s.station_name + '（気象官署）')
            : s.station_name;
        $sel.append($('<option>').val(s.block_no).text(label));
    });
    $sel.prop('disabled', false);

    if (selectBlockNo) {
        $sel.val(selectBlockNo);
    }
}

// 選択中の地点コードを画面に表示する
function sub910_onChangeStation() {
    var precNo = $('#sel_prec').val();
    var kansyoBlockNo = $('#sel_kansyo').val();
    var amedasBlockNo = $('#sel_amedas').val();

    $('#txt_kansyo_code').html(
        kansyoBlockNo ? ('prec_no: ' + precNo + ' / block_no: ' + kansyoBlockNo) : '&nbsp;'
    );
    $('#txt_amedas_code').html(
        amedasBlockNo ? ('prec_no: ' + precNo + ' / block_no: ' + amedasBlockNo) : '&nbsp;'
    );
}

function sub910_btnReset() {
    $('#sel_prec').val(sub910_initial.precNo);

    if (sub910_initial.precNo) {
        sub910_loadStations(
            sub910_initial.precNo,
            sub910_initial.kansyoBlockNo,
            sub910_initial.amedasBlockNo
        );
    } else {
        sub910_setStationOptions('#sel_kansyo', [], '');
        sub910_setStationOptions('#sel_amedas', [], '');
        sub910_onChangeStation();
    }
}

function sub910_btnSave() {
    var precNo = $('#sel_prec').val();
    var kansyoBlockNo = $('#sel_kansyo').val();
    var amedasBlockNo = $('#sel_amedas').val();

    if (!precNo || !kansyoBlockNo || !amedasBlockNo) {
        Swal.fire('確認', '都府県・気象官署・アメダスをすべて選択してください。', 'warning');
        return;
    }

    var isChanged = (precNo !== sub910_initial.precNo)
                 || (kansyoBlockNo !== sub910_initial.kansyoBlockNo)
                 || (amedasBlockNo !== sub910_initial.amedasBlockNo);

    if (!isChanged) {
        Swal.fire('確認', '設定は変更されていません。', 'info');
        return;
    }

    var kansyoName = $('#sel_kansyo option:selected').text();
    var amedasName = $('#sel_amedas option:selected').text();

    Swal.fire({
        title: '観測地点を変更しますか？',
        html: '気象官署: <b>' + kansyoName + '</b><br>'
            + 'アメダス: <b>' + amedasName + '</b><br><br>'
            + '<span style="color:#E74C3C;">取得済みの天候情報は以前の地点のまま残ります。</span><br>'
            + '変更後の地点でデータを取得できるか確認してから保存します。',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '確認して保存',
        cancelButtonText: 'キャンセル'
    }).then((result) => {
        if (result.isConfirmed) {
            sub910_postSave(precNo, kansyoBlockNo, amedasBlockNo);
        }
    });
}

function sub910_postSave(precNo, kansyoBlockNo, amedasBlockNo) {
    $('#btn_save').prop('disabled', true);

    Swal.fire({
        title: '気象庁への接続を確認しています',
        text: 'しばらくお待ちください...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode: 'save',
            precNo: precNo,
            blockNoKansyo: kansyoBlockNo,
            blockNoAmedas: amedasBlockNo
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    }).done(function (res) {
        if (res.save_success) {
            sub910_initial.precNo = precNo;
            sub910_initial.kansyoBlockNo = kansyoBlockNo;
            sub910_initial.amedasBlockNo = amedasBlockNo;
            sub910_updateCurrentTable(precNo, kansyoBlockNo, amedasBlockNo);

            Swal.fire({
                title: '保存しました',
                html: res.err_message,
                icon: 'success'
            });
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
        $('#btn_save').prop('disabled', false);
    });
}

// 保存に成功したら「現在の設定」の表を書き換える（再読込せずに済ませる）
function sub910_updateCurrentTable(precNo, kansyoBlockNo, amedasBlockNo) {
    $('#cur_kansyo_name').text($('#sel_kansyo option:selected').text());
    $('#cur_kansyo_prec').text(precNo);
    $('#cur_kansyo_block').text(kansyoBlockNo);

    $('#cur_amedas_name').text($('#sel_amedas option:selected').text());
    $('#cur_amedas_prec').text(precNo);
    $('#cur_amedas_block').text(amedasBlockNo);
}
