/*
    各画面専用javascript
    330ticket_data.html
    ※命名規則　sub330_xxxxxx (パッケージ等の共通関数と重複させない為)
*/


function initFor330(){
    // getKikan: 初期 month(月次)

    let initParam = {
        getMode:'init',
        getChartMode: sub330_getChartMode()
    };

    sub330_postView(initParam);
}


function sub330_postView(initParam){

    // view.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : initParam.getMode,
            getYM : initParam.getYM,
            getChartMode : initParam.getChartMode
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
        var totalTbl = [];
        var allDataTbl = [];
        var chartXLabels = [];

        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'initYMD':
                    $("#calendar_initval").val(val);
                    break;
                case 'firstDay':
                    $("#calendar_from").val(val);
                    break;
                case 'lastDay':
                    $("#calendar_to").val(val);
                    break;
                case 'xLabel':
                    chartXLabels = val;
                    break;
                case 'allTable':
                    allDataTbl = val;
                    break;
                case 'totalTable':
                    $.each(val, function(key2, val2) {
                        var tmp = [];
                    
                        $.each(val2, function(key3, val3) {
                            tmp[key3] = val3;
                        });

                        totalTbl.push(tmp);
                    });
                    break;
                default:
                    console.log('unknown key:' + key);
                    break;
            }
        });
                
        // グラフ処理
        sub330_setChartData(allDataTbl, chartXLabels);

        // 表の表示
        sub330_drawTable(totalTbl);

        // datepickerの設定
        sub330_setDatepicker(initParam.getMode);        

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

function sub330_setChartData(allDataTbl, chartXLabels){

    if(sub330_getChartMode() === 'month'){
        sub330_setChartDataM(allDataTbl);
    } else {
        sub330_setChartDataD(chartXLabels, allDataTbl);
    }

}

function sub330_setChartDataM(dataTbl){
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

    for(let i = 1; i < 13; i++){
        tmpXLabels.push(i.toString() + '月');

        if(i.toString().padStart(1, '0') in dataTbl){
            tmpData1.push(dataTbl[i.toString().padStart(1, '0')]['sales']);
        } else {
            tmpData1.push(0);
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
                order: 10,
                label: "Lineクーポン月間利用額",
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
                }
            }
        }
    });

}

function sub330_setChartDataD(chartXLabels, chart_plot_data){
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

    for (var key in chartXLabels) {
        tmpXLabels.push(chartXLabels[key]);
    };

    Object.keys(chart_plot_data).sort()

    for (var key in chart_plot_data) {
        tmpData1.push(chart_plot_data[key]);
    };

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
                label: "Lineクーポン利用額",
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
                x: {
                    ticks: {
                        autoSkip: false,
                        // コールバック関数を使ってラベルの色を動的に変更
                        color: function(context) {
                            return com_setChartLabelColor(context);
                        }
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'left',
                    title:{
                        display: false
                    },
                }
            }
        }
    });

}


function sub330_setDatepicker(getMode){

    if(sub330_getChartMode() === 'month'){
        sub330_setDatepickerY(getMode);
    } else {
        sub330_setDatepickerM(getMode);
    }

}


function sub330_setDatepickerY(getMode){

    if (getMode === 'init'){
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        var month = (newDate.getMonth() + 1).toString();
    
        // 設定値が確定するこの場所でdatepickerの設定をする(要改良)
        $.fn.datepicker.defaults.language = 'ja';
        $.fn.datepicker.defaults.startDate = new Date($("#calendar_from").val());
        $.fn.datepicker.defaults.endDate = new Date($("#calendar_to").val());
        $.fn.datepicker.defaults.minViewMode = 2;
        $.fn.datepicker.defaults.maxViewMode = 2;
        $.fn.datepicker.defaults.format = 'yyyy年';
        $.fn.datepicker.defaults.autoclose = true;
    
        sub330_init_daterangepicker_single_call_gf();
    
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年');
    
    } else {
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');

        // カレンダーのリセット処理----
        var $el = $('.input-group.date');
    
        // 現在の入力値を退避
        var currentVal = $el.val();
    
        // 【重要】destroyで一度リセットしてから再設定
        $el.datepicker('destroy').datepicker({
            minViewMode: 2, // 年選択に変更
            format:'yyyy年'            
        });
    
        // 値を戻して表示
        $el.val(currentVal);
        //---- カレンダーのリセット処理

        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年');
    }

    $("#calendar_saveval").val($("#gf_calendar").val());

}

function sub330_setDatepickerM(getMode){

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
        
        sub330_init_daterangepicker_single_call_gf();
        
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年' + month + '月');
        
    } else {
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        var month = (newDate.getMonth() + 1).toString();

        // カレンダーのリセット処理----
        var $el = $('.input-group.date');
    
        // 現在の入力値を退避
        var currentVal = $el.val();
    
        // 【重要】destroyで一度リセットしてから再設定
        $el.datepicker('destroy').datepicker({
            minViewMode: 1, // 月選択に変更
            format:'yyyy年MM'            
        });
    
        // 値を戻して表示
        $el.val(currentVal);
        //---- カレンダーのリセット処理

        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年' + month + '月');
    }

}


function sub330_init_daterangepicker_single_call_gf() {

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

            let initParam = {
                getMode:'get',
                getYM:com_convStrDateTime(obj.date) + ' 00:00:00',
                getChartMode:sub330_getChartMode()
            };
        
            sub330_postView(initParam);

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

function sub330_drawTable(tableData){

    var tmpColums = [];
    switch(sub330_getChartMode()){
        case 'day':
            tmpColums = [
                {data:"name"},
                {data:"value"}
            ]
            break;
        case 'month':
            tmpColums = [
                {data:"name"},
                {data:"value"}
            ]
            break;
        default:
            break;
    }

    var table=$('#datatable_gf').DataTable({
        'data'        :tableData,
        'paging'      :false,
        'pageLength'  :5,
        'lengthChange':false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'scrollX'     :true,
        'scrollCollapse': true,
        'destroy'       :true,
        'columns'     :tmpColums,

    }).on( 'draw.dt', function () {
        com_tableDataEditColor();
    } );

}

function sub330_btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    if(sub330_getChartMode() === 'month'){
        newDate.setMonth(newDate.getMonth() - 12);
    } else {
        newDate.setMonth(newDate.getMonth() - 1);
    }

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub330_getChartMode()
    };

    $('.input-group.date').datepicker('update', newDate);
    sub330_postView(initParam);

}

function sub330_btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    if(sub330_getChartMode() === 'month'){
        newDate.setMonth(newDate.getMonth() + 12);
    } else {
        newDate.setMonth(newDate.getMonth() + 1);
    }

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub330_getChartMode()
    };

    $('.input-group.date').datepicker('update', newDate);

    sub330_postView(initParam);

}

function btnToggleChartMode(){
    // 年間表示／月間表示の切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub330_getChartMode()
    };

    sub330_postView(initParam);

}

// 以下、共通処理
function sub330_getChartMode(){
    var result = $('input[name="chart_mode"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}


// 初期処理
$(document).ready(function() {
        initFor330();
    });
    
