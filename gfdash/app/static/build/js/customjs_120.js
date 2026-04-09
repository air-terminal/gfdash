/*
    各画面専用javascript
    120getuji_hikaku.html
    ※命名規則　sub120_xxxxxx (パッケージ等の共通関数と重複させない為)
*/


function initFor120(){
    let initParam = {
        getMode:'init'
    };

    sub120_postView(initParam);
}

function sub120_postView(initParam){

    // view.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : initParam.getMode,
            getYM : initParam.getYM
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
        var dataTbl = [];
        var allDataTbl = [];
        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'school1_name':
                    $("#school1-1").text(val);
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
                case 'yearTale':
                    dataTbl = val;
                    break;
                case 'allYearTable':
                    allDataTbl = val;
                    break;
                case 'mm':
                    $("#txt001").text(val + "月来場者数");
                    break;
                default:
                    console.log('unknown key:' + key);
                    break;
            }
        });
                
        // グラフ処理
        sub120_setChartData(dataTbl, allDataTbl);

        // 表の表示
        sub120_drawTable(dataTbl, allDataTbl);
        com_tableDataEditColor();

        // datepickerの設定
        sub120_setDatepicker(initParam.getMode);

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

function sub120_setChartData(dataTbl, allDataTbl){
    //　グラフ表示処理

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

    var tmpXLabels = [];
    var tmpData1 = [];
    var tmpSuggestedMinY = 0;
    var tmpBaseAll = 0;

    // Y軸最小値(仮)
    $.each(dataTbl, function(key, val) {
        tmpSuggestedMinY = val['all'];
        tmpBaseAll = val['all'];
    });
    
    // 月別来場者数
    $.each(allDataTbl, function(key, val) {
        tmpXLabels.push(key + '年');
        tmpData1.push(val['all']);
        if (tmpSuggestedMinY > val['all']){
            tmpSuggestedMinY = val['all'];
        }
    });

    // Y軸表記最小値計算
    tmpSuggestedMinY = Math.floor(tmpSuggestedMinY / 1000) * 1000 - 1000; 
    if(tmpSuggestedMinY < 0){
        tmpSuggestedMinY = 0;
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
                order: 10,
                label: "月間来場者数",
                backgroundColor: "rgba(38, 185, 154, 0.7)",
                borderColor: "rgba(38, 185, 154, 0.7)",
                pointBorderColor: "rgba(38, 185, 154, 0.7)",
                pointBackgroundColor: "rgba(38, 185, 154, 0.7)",
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(220,220,220,1)",
                pointBorderWidth: 1,
                fill: true,
                data: tmpData1,
                yAxisID: 'y1',
                tension: 0,
                type: 'bar'
            }]
        },
        options: {
            scales: {
                y1: {
                    type: 'linear',
                    position: 'left',
                    title:{
                        display: false
                    },
                    min: tmpSuggestedMinY
                }
            },
            plugins:{
                annotation: {
                    annotations: {
                        line1: {
                            type: 'line',
                            yMin: tmpBaseAll,
                            yMax: tmpBaseAll,
                            borderColor: "rgba(3, 88, 106, 0.70)",
                            borderWidth: 2,
                            label: {
                                enabled: true
                            }
                        },
                    }
                }

            }
        }
    });

}


function sub120_setDatepicker(getMode){

    if (getMode === 'init'){
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        var month = (newDate.getMonth() + 1).toString();
    
        // 設定値が確定するこの場所でdatepickerの設定をする(要改良)
        $.fn.datepicker.defaults.language = 'ja';
        $.fn.datepicker.defaults.startDate = new Date($("#calendar_from").val());
        $.fn.datepicker.defaults.endDate = new Date($("#calendar_to").val());
        $.fn.datepicker.defaults.minViewMode = 1;
        $.fn.datepicker.defaults.maxViewMode = 2;
        $.fn.datepicker.defaults.format = 'yyyy年MM';
        $.fn.datepicker.defaults.autoclose = true;
    
        sub120_init_daterangepicker_single_call_gf();
    
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年' + month + '月');
    
    } else {
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        var month = (newDate.getMonth() + 1).toString();
        $("#gf_calendar").val(year + '年' + month + '月');
    }

    $("#calendar_saveval").val($("#gf_calendar").val());

}

function sub120_init_daterangepicker_single_call_gf() {

    if (typeof($.fn.datepicker) === 'undefined') {
        return;
    }
    
    $('.input-group.date').datepicker({
        format: 'yyyy年',
        keyboardNavigation: false,
        autoclose: true
    }).on({
        changeDate:
          function(obj) {

            $("#calendar_saveval").val($("#gf_calendar").val());

            let initParam = {
                getMode:'get',
                getYM:com_convStrDateTime(obj.date) + ' 00:00:00'
            };
        
            sub120_postView(initParam);

            var newDate = new Date(initParam.getYM);
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();
            $("#gf_calendar").val(year + '年');
            $("#calendar_saveval").val($("#gf_calendar").val());

        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}


function sub120_drawTable(dataTbl, allDataTbl){

    var tmpBaseSum = 0;
    var tmpBaseYear = '';

    // ベースデータの取得
    $.each(dataTbl, function(key, val) {
        tmpBaseYear = key;
        $.each(val, function(key2, val2) {
            if(key2 === 'all'){
                tmpBaseSum = val2;
            }
        });
    });

    // 表データの生成
    var tmpData = [];
    $.each(allDataTbl, function(key, val) {

        var tmp = [];
        if(key === tmpBaseYear){
            tmp['business_y'] = '▶' + key + '年';
            $("#default_year").text(key + '年比');
        } else {
            tmp['business_y'] = key + '年';
        };

        $.each(val, function(key2, val2) {
            tmp[key2] = val2;
        });
        tmp['hikaku'] = tmpBaseSum - val['all'];
        tmpData.push(tmp);

    });

    tmpData.reverse();

    var table=$('#datatable_gf').DataTable({
        'data'        :tmpData,
        'paging'      :false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :false, // 重要：自動計算をOFF
        'destroy'     :true,
        'columns'     :[
            {data:"business_y",      width: "10.6%"}, // 年
            {data:"morning",         width: "9.1%"}, // 朝
            {data:"afternoon",       width: "9.1%"}, // 昼
            {data:"night",           width: "9.1%"}, // 夜
            {data:"school",          width: "9.6%"},   // スクール
            {data:"int_school",      width: "10.1%"}, // (内部S)
            {data:"member",          width: "9.6%"},   // メンバー
            {data:"visitor",         width: "9.6%"},   // ビジター
            {data:"all",             width: "11.6%"},  // 合計
            {data:"hikaku",          width: "11.6%"}   // 基準比
        ]
    }).on( 'draw.dt', function () {
        com_tableDataEditColor();
    });

    // 描画後に幅を再調整
    setTimeout(function(){
        table.columns.adjust();
    }, 50);

}

function sub120_btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);
    sub120_postView(initParam);

}

function sub120_btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);

    sub120_postView(initParam);

}

// 初期処理
$(document).ready(function() {
        initFor120();
    });
    
