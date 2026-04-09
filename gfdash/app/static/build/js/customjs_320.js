/*
    各画面専用javascript
    320tanka_data.html
    ※命名規則　sub320_xxxxxx (パッケージ等の共通関数と重複させない為)
*/


function initFor320(){

    let initParam = {
        getMode:'init'
    };

    sub320_postView(initParam);

    // icheck使用部のイベントリスナー定義
    $('input').on('ifChecked', function(event){
        switch($(this).attr('name')){
            case 'option1_tanka':
                btnToggleOprion1();
                break;
            case 'option2_detail':
                btnToggleOprion2();
                break;
        }
    });


}


function sub320_postView(initParam){

    // view.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : initParam.getMode,
            getYM : initParam.getYM,
            getChartMode : sub320_getChartMode(),
            getDetail : sub320_getOption2()
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
        var oldDataTbl = [];
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
                case 'yearTable':
                    dataTbl = val;
                    break;
                case 'allYearTable':
                    allDataTbl = val;
                    break;
                case 'oldYearTable':
                    oldDataTbl = val;
                    break;
                default:
                    console.log('unknown key:' + key);
                    break;
            }
        });
                
        // グラフ処理
        sub320_setChartData(dataTbl, allDataTbl);

        // 表の表示
        sub320_drawTable(dataTbl, allDataTbl, oldDataTbl);
        com_tableDataEditColor();

        // datepickerの設定
        sub320_setDatepicker(initParam.getMode);        

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

function sub320_setChartData(dataTbl, allDataTbl){

    if(sub320_getChartMode() === 'year'){
        sub320_setChartDataY(dataTbl, allDataTbl);
    } else if(sub320_getChartMode() === 'month'){
        sub320_setChartDataM(allDataTbl);
    } else if(sub320_getChartMode() === 'cf_month'){
        sub320_setChartDataCfM(dataTbl, allDataTbl);
    } else {
        sub320_setChartDataD(dataTbl);
    }

}

function sub320_setChartDataY(dataTbl, allDataTbl){
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
    var tmpSuggestedMinY = 0;
    var tmpBaseAll = 0;

    var tmpDatasets = [];
    var tmpDataX1 = [];
    var tmpDataX2 = [];
    var tmpDataX1Color = "rgba(38, 185, 154, 0.7)";
    var tmpDataX2Color = "rgba(52,152,219,0.7)";
    var tmpArryName1 = 'tanka';
    var tmpArryName2 = 'tanka';

    if (sub320_getOption1() === 'add_coupon'){
        if (sub320_getOption2() === 'gross'){
            tmpArryName1 = 'tanka';
        } else {
            tmpArryName1 = 'nebikimae_tanka';
        }
    } else {
        tmpArryName1 = 'tanka';
    }

    if (sub320_getOption1() === 'uriage'){
        tmpArryName2 = 'tanka';
    } else {
        tmpArryName2 = 'nebikimae_tanka';
    }

    // Y軸最小値(仮)
    $.each(dataTbl, function(key, val) {
        tmpSuggestedMinY = val[tmpArryName1];
        tmpBaseAll = val[tmpArryName2];
    });
    
    // 年別単価
    $.each(allDataTbl, function(key, val) {
        tmpXLabels.push(key + '年');
        tmpDataX1.push(val[tmpArryName1]);
        if (tmpSuggestedMinY > val[tmpArryName1]){
            tmpSuggestedMinY = val[tmpArryName1];
        }
    });

    tmpDatasets.push({
        order: 100,
        stack: 'stack1',
        label: "客単価（年間）",
        backgroundColor: tmpDataX1Color,
        borderColor: tmpDataX1Color,
        pointBorderColor: tmpDataX1Color,
        pointBackgroundColor: tmpDataX1Color,
        pointHoverBackgroundColor: "#fff",
        pointHoverBorderColor: "rgba(220,220,220,1)",
        pointBorderWidth: 1,
        fill: true,
        data: tmpDataX1,
        yAxisID: 'y1',
        tension: 0,
        type: 'bar'
    });


    // 値引き前単価(積み上げグラフ差分値)
    if (sub320_getOption1() === 'add_coupon' && sub320_getOption2() === 'gross'){
        $.each(allDataTbl, function(key, val) {
            tmpDataX2.push(val['nebikimae_tanka'] - val['tanka']);
        });

        tmpDatasets.push({
                    order: 101,
                    stack: 'stack1',
                    label: "券/クーポン",
                    backgroundColor: tmpDataX2Color,
                    borderColor: tmpDataX2Color,
                    pointBorderColor: tmpDataX2Color,
                    pointBackgroundColor: tmpDataX2Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX2,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    }

    // Y軸表記最小値計算
    tmpSuggestedMinY = Math.floor(tmpSuggestedMinY / 100) * 100 - 100; 
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
            datasets: tmpDatasets
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


function sub320_setChartDataM(allDataTbl){
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
    var tmpSuggestedMinY = 1000000;

    var tmpDatasets = [];
    var tmpDataX1 = [];
    var tmpDataX2 = [];
    var tmpDataX1Color = "rgba(38, 185, 154, 0.7)";
    var tmpDataX2Color = "rgba(52,152,219,0.7)";

    for(let i = 1; i < 13; i++){
        tmpXLabels.push(i.toString() + '月');

        if(i.toString() in allDataTbl){
            tmpDataX1.push(allDataTbl[i.toString()]['tanka']);
            tmpDataX2.push(allDataTbl[i.toString()]['nebikimae_tanka'] - allDataTbl[i.toString()]['tanka']);

            if (tmpSuggestedMinY > allDataTbl[i.toString()]['tanka']){
                tmpSuggestedMinY = allDataTbl[i.toString()]['tanka'];
            }

        } else {
            tmpDataX1.push(0);
            tmpDataX2.push(0);
        }
    }

    // Y軸表記最小値計算
    tmpSuggestedMinY = Math.floor(tmpSuggestedMinY / 50) * 50; 
    if(tmpSuggestedMinY < 0){
        tmpSuggestedMinY = 0;
    }

    if (!$("#chart_plot_mix").length) {
        return;
    }

    // 客単価
    tmpDatasets.push({
        order: 100,
        stack: 'stack1',
        label: "客単価（年間）",
        backgroundColor: tmpDataX1Color,
        borderColor: tmpDataX1Color,
        pointBorderColor: tmpDataX1Color,
        pointBackgroundColor: tmpDataX1Color,
        pointHoverBackgroundColor: "#fff",
        pointHoverBorderColor: "rgba(220,220,220,1)",
        pointBorderWidth: 1,
        fill: true,
        data: tmpDataX1,
        yAxisID: 'y1',
        tension: 0,
        type: 'bar'
    });

    // 値引き前単価(積み上げグラフ差分値)
    if (sub320_getOption1() === 'add_coupon'){
        tmpDatasets.push({
                    order: 101,
                    stack: 'stack1',
                    label: "券/クーポン",
                    backgroundColor: tmpDataX2Color,
                    borderColor: tmpDataX2Color,
                    pointBorderColor: tmpDataX2Color,
                    pointBackgroundColor: tmpDataX2Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX2,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    }

    var ctx = document.getElementById("chart_plot_mix");
    window.Chart1 = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tmpXLabels,
            datasets: tmpDatasets
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
            }
        }
    });

}

function sub320_setChartDataCfM(dataTbl, allDataTbl){
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
    var tmpSuggestedMinY = 1000000;
    var tmpBaseAll = 0;

    var tmpDatasets = [];
    var tmpDataX1 = [];
    var tmpDataX2 = [];
    var tmpDataX1Color = "rgba(38, 185, 154, 0.7)";
    var tmpDataX2Color = "rgba(52,152,219,0.7)";
    var tmpArryName = 'tanka';
    if (sub320_getOption1() === 'uriage'){
        tmpArryName = 'tanka';
    } else {
        tmpArryName = 'nebikimae_tanka';
    }

    // Y軸最小値(仮)
    $.each(dataTbl, function(key, val) {
        tmpSuggestedMinY = val['tanka'];
        tmpBaseAll = val[tmpArryName];
    });
    
    // 年別単価
    $.each(allDataTbl, function(key, val) {
        tmpXLabels.push(key + '年');
        tmpDataX1.push(val['tanka']);
        if (tmpSuggestedMinY > val['tanka']){
            tmpSuggestedMinY = val['tanka'];
        }
    });

    tmpDatasets.push({
        order: 100,
        stack: 'stack1',
        label: "客単価（月比較）",
        backgroundColor: tmpDataX1Color,
        borderColor: tmpDataX1Color,
        pointBorderColor: tmpDataX1Color,
        pointBackgroundColor: tmpDataX1Color,
        pointHoverBackgroundColor: "#fff",
        pointHoverBorderColor: "rgba(220,220,220,1)",
        pointBorderWidth: 1,
        fill: true,
        data: tmpDataX1,
        yAxisID: 'y1',
        tension: 0,
        type: 'bar'
    });

    // 値引き前単価(積み上げグラフ差分値)
    if (sub320_getOption1() === 'add_coupon'){
        $.each(allDataTbl, function(key, val) {
            tmpDataX2.push(val['nebikimae_tanka'] - val['tanka']);
        });

        tmpDatasets.push({
                    order: 101,
                    stack: 'stack1',
                    label: "券/クーポン",
                    backgroundColor: tmpDataX2Color,
                    borderColor: tmpDataX2Color,
                    pointBorderColor: tmpDataX2Color,
                    pointBackgroundColor: tmpDataX2Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX2,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    }

    // Y軸表記最小値計算
    tmpSuggestedMinY = Math.floor(tmpSuggestedMinY / 50) * 50; 
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
            datasets: tmpDatasets
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


function sub320_setChartDataD(dataTbl){
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
    var tmpSuggestedMinY = 1000000;

    var tmpDatasets = [];
    var tmpDataX1 = [];
    var tmpDataX2 = [];
    var tmpDataX1Color = "rgba(38, 185, 154, 0.7)";
    var tmpDataX2Color = "rgba(52,152,219,0.7)";

    $.each(dataTbl, function(key, val) {
        tmpXLabels.push(key);

        tmpDataX1.push(val['tanka']);
        tmpDataX2.push(val['nebikimae_tanka'] - val['tanka']);

        if(key != "祝日" || val['tanka'] > 0){

            if (tmpSuggestedMinY > val['tanka']){
                tmpSuggestedMinY = val['tanka'];
            }

        }


    });

    // Y軸表記最小値計算
    tmpSuggestedMinY = Math.floor(tmpSuggestedMinY / 100) * 100; 
    if(tmpSuggestedMinY < 0){
        tmpSuggestedMinY = 0;
    }

    if (!$("#chart_plot_mix").length) {
        return;
    }

    // 客単価
    tmpDatasets.push({
        order: 100,
        stack: 'stack1',
        label: "客単価（月間）",
        backgroundColor: tmpDataX1Color,
        borderColor: tmpDataX1Color,
        pointBorderColor: tmpDataX1Color,
        pointBackgroundColor: tmpDataX1Color,
        pointHoverBackgroundColor: "#fff",
        pointHoverBorderColor: "rgba(220,220,220,1)",
        pointBorderWidth: 1,
        fill: true,
        data: tmpDataX1,
        yAxisID: 'y1',
        tension: 0,
        type: 'bar'
    });

    // 値引き前単価(積み上げグラフ差分値)
    if (sub320_getOption1() === 'add_coupon'){
        tmpDatasets.push({
                    order: 101,
                    stack: 'stack1',
                    label: "券/クーポン",
                    backgroundColor: tmpDataX2Color,
                    borderColor: tmpDataX2Color,
                    pointBorderColor: tmpDataX2Color,
                    pointBackgroundColor: tmpDataX2Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX2,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    }


    var ctx = document.getElementById("chart_plot_mix");
    window.Chart1 = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tmpXLabels,
            datasets: tmpDatasets
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
            }
        }
    });

}


function sub320_setDatepicker(getMode){

    if(sub320_getChartMode() === 'year'){
        sub320_setDatepickerY(getMode);
    } else if(sub320_getChartMode() === 'month'){
        sub320_setDatepickerY(getMode);
    } else {
        sub320_setDatepickerM(getMode);
    }

}


function sub320_setDatepickerY(getMode){

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
    
        sub320_init_daterangepicker_single_call_gf();
    
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

function sub320_setDatepickerM(getMode){

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
        
        sub320_init_daterangepicker_single_call_gf();
        
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

    $("#calendar_saveval").val($("#gf_calendar").val());

}


function sub320_init_daterangepicker_single_call_gf() {

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

            let initParam = {
                getMode:'get',
                getYM:com_convStrDateTime(obj.date) + ' 00:00:00'
            };
        
            sub320_postView(initParam);

        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}

function sub320_drawTable(dataTbl, allDataTbl, oldDataTbl){

    if(sub320_getChartMode() === 'year'){
        sub320_drawTableY(dataTbl, allDataTbl);
    } else if(sub320_getChartMode() === 'month') {
        sub320_drawTableM(allDataTbl, oldDataTbl);
    } else if(sub320_getChartMode() === 'cf_month') {
        sub320_drawTableCfM(dataTbl, allDataTbl);
    } else {
        sub320_drawTableD(dataTbl);
    }

}

function sub320_drawTableY(dataTbl, allDataTbl){

    var tmpBaseSum = 0;
    var tmpBaseYear = '';

    var tmpArryName = 'tanka';
    if (sub320_getOption1() === 'uriage'){
        tmpArryName = 'tanka';
    } else {
        tmpArryName = 'nebikimae_tanka';
    }

    $("#table_foother").hide();
    $("#head_txt1").text('年');

    // ベースデータの取得
    $.each(dataTbl, function(key, val) {
        tmpBaseYear = key;
        $.each(val, function(key2, val2) {
            if(key2 === tmpArryName){
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
        tmp['hikaku'] = (tmpBaseSum - val[tmpArryName]).toFixed(2);
        tmpData.push(tmp);

    });

    tmpData.reverse();

    var table=$('#datatable_gf').DataTable({
        'data'        :tmpData,
        'paging'      :false,
        'pageLength'  :5,
        'lengthChange':false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :true,
        'scrollX'     :false,
        'scrollY'     :false,
        destroy: true,
        'columns'     :[
            {data:"business_y"},
            {data:tmpArryName},
            {data:"hikaku"}
        ]

    } );
}

function sub320_drawTableM(allDataTbl, oldDataTbl){

    $("#head_txt1").text('月');
    $("#default_year").text('前年比');
    $("#table_foother").show();

    var tmpArryName = 'tanka';
    if (sub320_getOption1() === 'uriage'){
        tmpArryName = 'tanka';
    } else {
        tmpArryName = 'nebikimae_tanka';
    }

    // 表データの生成
    var tmpData = [];
    var tmp = [];

    var tmpTanka = 0;
    var tmpOldTanka = 0;

    for(let i = 1; i < 13; i++){
        tmp = [];
        tmp['business_m'] = i.toString() + '月';
        tmpOldTanka = 0;

        if(i.toString() in allDataTbl){
            tmpTanka = allDataTbl[i.toString()]['tanka'];
        } else {
            tmpTanka = 0;
        }

        $.each(oldDataTbl, function(key, val) {
            if(key === i.toString()){
                tmpOldTanka = val['tanka'];
            };
        });

        tmp['tanka'] = tmpTanka;

        if(tmpTanka > 0) {
            tmp['hikaku'] = (tmpTanka - tmpOldTanka).toFixed(2);
        } else {
            tmp['tanka'] = "";
            tmp['hikaku'] = "";
        }

        tmpData.push(tmp);
    }

    var table=$('#datatable_gf').DataTable({
        'data'        :tmpData,
        'paging'      :false,
        'pageLength'  :5,
        'lengthChange':false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :true,
        'scrollX'     :false,
        'scrollY'     :false,
        destroy: true,
        'columns'     :[
            {data:"business_m"},
            {data:"tanka"},
            {data:"hikaku"}
        ]

    } );
}

function sub320_drawTableCfM(dataTbl, allDataTbl){
    sub320_drawTableY(dataTbl, allDataTbl);
}

function sub320_drawTableD(dataTbl){

    var tmpBaseSum = 0;
    var tmpBaseYear = '';

    var tmpArryName = 'tanka';
    if (sub320_getOption1() === 'uriage'){
        tmpArryName = 'tanka';
    } else {
        tmpArryName = 'nebikimae_tanka';
    }

    $("#table_foother").hide();
    $("#head_txt1").text('曜日');
    $("#default_year").text('');

    // ベースデータの取得
    $.each(dataTbl, function(key, val) {
        tmpBaseYear = key;
        $.each(val, function(key2, val2) {
            if(key2 === tmpArryName){
                tmpBaseSum = val2;
            }
        });
    });

    // 表データの生成
    var tmpData = [];
    $.each(dataTbl, function(key, val) {

        var tmp = [];
        tmp['weekdayName'] = key;

        $.each(val, function(key2, val2) {
            tmp[key2] = val2;
        });
        tmp['hikaku'] = '';
        tmpData.push(tmp);

    });

//    tmpData.reverse();

    var table=$('#datatable_gf').DataTable({
        'data'        :tmpData,
        'paging'      :false,
        'pageLength'  :5,
        'lengthChange':false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :true,
        'scrollX'     :false,
        'scrollY'     :false,
        destroy: true,
        'columns'     :[
            {data:"weekdayName"},
            {data:tmpArryName},
            {data:"hikaku"}
        ]

    } );
}



function sub320_btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    if(sub320_getChartMode() === 'year'){
        newDate.setMonth(newDate.getMonth() - 12);
    } else if(sub320_getChartMode() === 'month'){
        newDate.setMonth(newDate.getMonth() - 12);
    } else {
        newDate.setMonth(newDate.getMonth() - 1);
    }

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);
    sub320_postView(initParam);

}

function sub320_btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    if(sub320_getChartMode() === 'year'){
        newDate.setMonth(newDate.getMonth() + 12);
    } else if(sub320_getChartMode() === 'month'){
        newDate.setMonth(newDate.getMonth() + 12);
    } else {
        newDate.setMonth(newDate.getMonth() + 1);
    }

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);

    sub320_postView(initParam);

}

function btnToggleChartMode(){
    // 年間表示／月間表示の切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00'
    };

    sub320_postView(initParam);

}

function btnToggleOprion1(){
    // 年会費の集計先切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00'
    };

    sub320_postView(initParam);

    if (sub320_getOption1() === 'uriage' &&  sub320_getOption2() != "gross"){
        $('#option2_id01').iCheck('check');
    }
}

function btnToggleOprion2(){
    // グラフオプション切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00'
    };

    if (sub320_getOption1() === 'uriage' &&  sub320_getOption2() != "gross"){
        $('#option1_id02').iCheck('check');
    }

    sub320_postView(initParam);
}


// 以下、共通処理
function sub320_getChartMode(){
    var result = $('input[name="chart_mode"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}

function sub320_getOption1(){
    var result = $('input[name="option1_tanka"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}

function sub320_getOption2(){
    var result = $('input[name="option2_detail"]:checked');
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
        initFor320();
    });
    
