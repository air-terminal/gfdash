/*
    各画面専用javascript
    340zennen_hikaku.html
    ※命名規則　sub340_xxxxxx (パッケージ等の共通関数と重複させない為)
*/

function initFor340(){
    let initParam = {
        getMode:'init'
    };

    sub340_postView(initParam);
}

function sub340_postView(initParam){

    // view.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : initParam.getMode,
            getY: initParam.getY
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
            // NProgress処理
            if (typeof NProgress != 'undefined') {
                NProgress.start();
            }   
        },
    }).done(function (results) {
        var tmp = [];
        var ninzuData = [];
        var uriageData = [];
        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'txtHeader':
                    $("#gf_header").text(val);
                    break;
                case 'initYMD':
                    $("#calendar_initval").val(val);
                    break;
                case 'firstDay':
                    $("#calendar_from").val(val);
                    break;
                case 'lastDay':
                    $("#calendar_to").val(val);
                    break;
                case 'ninzuData':
                    ninzuData = val;
                    break;
                case 'uriageData':
                    uriageData = val;
                    break;
                default:
//                    console.log('unknown key:' + key);
                    break;
            }
        });

        // グラフ処理
        sub340_setChartData(ninzuData, uriageData);

        // 表の表示
        sub340_drawHikakuTable(ninzuData, uriageData);

        // datepickerの設定
        sub340_setDatepicker(initParam.getMode);

        //ボタンの設定
        var initDate = new Date($("#calendar_initval").val());
        var fromDate = new Date($("#calendar_from").val());
        var toDate = new Date($("#calendar_to").val());

        fromDate.setDate(1);
        toDate.setDate(1);

        if (initDate.getTime() > fromDate.getTime()){
            $('#tbn_prev_month').prop('disabled',false);
        } else {
            $('#tbn_prev_month').prop('disabled',true);
        }

        if (initDate.getTime() < toDate.getTime()){
            $('#tbn_next_month').prop('disabled',false);
        } else {
            $('#tbn_next_month').prop('disabled',true);
        }
        

    }).fail(function (jqXHR, textStatus, errorThrown) {
        // 通信失敗時の処理
        console.log("ajax通信に失敗しました");
        console.log("jqXHR          : " + jqXHR.status); // HTTPステータスが取得
        console.log("textStatus     : " + textStatus);    // タイムアウト、パースエラー
        console.log("errorThrown    : " + errorThrown.message); // 例外情報
    });

    // NProgress終了処理
    if (typeof NProgress != 'undefined') {
        NProgress.done();
    }   

    return false;
}

//グラフ処理
function sub340_setChartData(ninzuData, uriageData){
    //値設定処理

    if (typeof(Chart) === 'undefined') {
        console.log('Chart undefined');
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    Chart.defaults.legend = {
        enabled: false
    };

    var tmpXLabels = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
    var tmpData1 = [];
    var tmpData2 = [];
    var tmpHanrei1 = '来場者数(全体)';
    var tmpHanrei2 = '売上(全体)';

    var tmpDataX1Color = "rgba(38,185,154,0.7)";
    var tmpDataX2Color = "rgba(52,152,219,0.7)";

    // --- 追加：データなしとなる最初のインデックスを保持する変数 ---
    var noDataIndex = null;

    // 1月〜12月までのループに切り替え、順番を保証しつつデータをセット
    for (var i = 1; i <= 12; i++) {
        var m = i.toString();
        
        // --- 来場者のデータセット ---
        if (ninzuData && ninzuData[m]) {
            var dN = ninzuData[m];
            if (dN.all == 100 && dN.range == 100 && dN.school == 100) {
                tmpData1.push(null); // データなしとして扱う（線を描画しない）
                if (noDataIndex === null) {
                    noDataIndex = i - 1; // 最初のデータなし月のインデックス(0始まり)を記録
                }
            } else {
                tmpData1.push(dN.all);
            }
        } else {
            tmpData1.push(null);
        }

        // --- 売上(全体)のデータセット ---
        if (uriageData && uriageData[m]) {
            var dU = uriageData[m];
            if (dU.all == 100 && dU.range == 100 && dU.school == 100) {
                tmpData2.push(null); // データなしとして扱う（線を描画しない）
            } else {
                tmpData2.push(dU.all);
            }
        } else {
            tmpData2.push(null);
        }
    }

    if (!$("#chart_plot_mix").length) {
        return;
    }

    var ctx = document.getElementById("chart_plot_mix");
    window.Chart1 = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tmpXLabels,
            datasets: [{
                order: 1,
                label: tmpHanrei1,
                borderColor: tmpDataX1Color,
                pointBorderColor: tmpDataX1Color,
                pointBackgroundColor: tmpDataX1Color,
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(220,220,220,1)",
                pointBorderWidth: 1,
                fill: false,
                data: tmpData1,
                yAxisID: 'y1',
                // ★追加: カスタムプラグインが読み取るためのプロパティ
                lineAtIndex: noDataIndex 
            }, {
                order: 3,
                label: tmpHanrei2,
                borderColor: tmpDataX2Color,
                pointBorderColor: tmpDataX2Color,
                pointBackgroundColor: tmpDataX2Color,
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(3,88,106,0.70)",
                pointBorderWidth: 1,
                fill: false,
                data: tmpData2,
                yAxisID: 'y1'
            }]
        },

        options: {
            // spanGaps: false, // （参考）途切れた箇所をつなぐかどうかの設定。false(デフォルト)で途切れます
            scales: {
                y1: {
                    type: 'linear',
                    position: 'left',
                    title:{
                        display: true,
                        text: '前年比'
                    },
                    max: (120),
                    min: (80)
                }
            },
            plugins: {
                annotation: {
                    annotations: {
                        line1: {
                            type: 'line',
                            yScaleID: 'y1', 
                            yMin: 100,
                            yMax: 100,
                            borderColor: 'rgb(255, 99, 132)',
                            borderWidth: 2,
                        }
                    }
                }
            }
        },
        // ★追加: カスタムプラグインをChart.jsに適用させる
        plugins: [verticalLinePlugin]
    });
}

// 比較テーブル描画処理（新規追加）@gemini作成
function sub340_drawHikakuTable(ninzuData, uriageData) {
    // 1月〜12月の配列
    var months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

    // --- ① ヘッダー行（月）の生成 ---
    // 横スクロールを防ぐため、min-width と nowrap を削除し、幅をパーセント(%)で指定します。
    // 「項目/月」を約16%、1〜12月を各約7%に割り当てます。
    var theadHtml = '<tr><th class="text-center" style="width: 16%; padding: 5px; font-size: 0.9em;">月</th>';
    for (var i = 0; i < months.length; i++) {
        theadHtml += '<th class="text-center" style="width: 7%; padding: 5px; font-size: 0.9em;">' + months[i] + '月</th>';
    }
    theadHtml += '</tr>';

    // --- ② 来場者行の生成 ---
    var ninzuHtml = '<tr><th style="padding: 5px; font-size: 0.9em; vertical-align: middle;">来場者数(全体)</th>';
    for (var i = 0; i < months.length; i++) {
        var m = months[i].toString();
        var val = '-'; // デフォルトはデータ無し

        if (ninzuData && ninzuData[m]) {
            var d = ninzuData[m];
            // 「all」「range」「school」が全て100の場合はデータなしとする
            if (d.all == 100 && d.range == 100 && d.school == 100) {
                val = '-';
            } else if (d.all !== undefined) {
                val = d.all;
            }
        }
        ninzuHtml += '<td class="text-right" style="padding: 5px; font-size: 0.9em; vertical-align: middle;">' + val + '</td>';        
    }
    ninzuHtml += '</tr>';

    // --- ③ 売上行の生成 ---
    var uriageHtml = '<tr><th style="padding: 5px; font-size: 0.9em; vertical-align: middle;">売上(全体)</th>';
    for (var i = 0; i < months.length; i++) {
        var m = months[i].toString();
        var val = '-'; // デフォルトはデータ無し

        if (uriageData && uriageData[m]) {
            var d = uriageData[m];
            // 「all」「range」「school」が全て100の場合はデータなしとする
            if (d.all == 100 && d.range == 100 && d.school == 100) {
                val = '-';
            } else if (d.all !== undefined) {
                val = d.all;
            }
        }
        uriageHtml += '<td class="text-right" style="padding: 5px; font-size: 0.9em; vertical-align: middle;">' + val + '</td>';        
    }
    uriageHtml += '</tr>';

    // --- ④ テーブル全体の組み立て ---
    // 【重要】table-layout: fixed; を追加することで、テーブルが親要素の幅(100%)を絶対超えないようにします。
    // word-wrap: break-word; で万が一文字が溢れそうになったら改行させます。
    var tableHtml = '<table class="table table-bordered table-striped" style="width: 100%; margin-bottom: 0; table-layout: fixed; word-wrap: break-word;">' +
                    '<thead class="bg-light">' + theadHtml + '</thead>' +
                    '<tbody>' + ninzuHtml + uriageHtml + '</tbody>' +
                    '</table>';

    // --- ⑤ コンテナにHTMLをセットして表示 ---
    var $container = $('#hikaku_table_container');
    $container.html(tableHtml);
    $container.show();
}


function sub340_setDatepicker(getMode){

    if (getMode === 'init'){
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
    
        // 設定値が確定するこの場所でdatepickerの設定をする(要改良)
        $.fn.datepicker.defaults.language = 'ja';
        $.fn.datepicker.defaults.startDate = new Date($("#calendar_from").val());
        $.fn.datepicker.defaults.endDate = new Date($("#calendar_to").val());
        $.fn.datepicker.defaults.minViewMode = 2;
        $.fn.datepicker.defaults.maxViewMode = 2;
        $.fn.datepicker.defaults.format = 'yyyy年';
        $.fn.datepicker.defaults.autoclose = true;
    
        sub340_init_daterangepicker_single_call_gf();
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年');
    
    } else {
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
//        var month = (newDate.getMonth() + 1).toString();
        $("#gf_calendar").val(year + '年');
    }

    $("#calendar_saveval").val($("#gf_calendar").val());

}

function sub340_init_daterangepicker_single_call_gf() {

    if (typeof($.fn.datepicker) === 'undefined') {
        return;
    }
    
    $('.input-group.date').datepicker({
        format: 'yyyy年',
        minViewMode: 2,
        keyboardNavigation: false,
        autoclose: true
    }).on({
        changeDate:
          function(obj) {

            $("#calendar_saveval").val($("#gf_calendar").val());

            let tmpParam = {
                getMode:'get',
                getY:com_convStrDateTime(obj.date) + ' 00:00:00'
            };
        
            sub340_postView(tmpParam);

        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}

function sub340_btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 12);

    let initParam = {
        getMode:'get',
        getY:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);
    sub340_postView(initParam);

}

function sub340_btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 12);

    let initParam = {
        getMode:'get',
        getY:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);

    sub340_postView(initParam);

}

// 初期処理
$(document).ready(function() {
        initFor340();
    });
    
