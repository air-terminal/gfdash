/*
    各画面専用javascript
    310nenkaihi_data.html
    ※命名規則　sub310_xxxxxx (パッケージ等の共通関数と重複させない為)
*/


function initFor310(){
    // getKikan: 初期 month(月次)

    let initParam = {
        getMode:'init',
        getChartMode: sub310_getChartMode()
    };

    sub310_postView(initParam);
}


function sub310_postView(initParam){

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
        var tmp = [];
        var dataTbl = [];
        var allDataTbl = [];
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
                case 'yearTale':
                    dataTbl = val;
                    break;
                case 'allYearTable':
                    allDataTbl = val;
                    break;
                default:
                    console.log('unknown key:' + key);
                    break;
            }
        });
                
        // グラフ処理
        sub310_setChartData(dataTbl, allDataTbl);

        // 表の表示
        sub310_drawTable(dataTbl, allDataTbl);
        com_tableDataEditColor();

        // datepickerの設定
        sub310_setDatepicker(initParam.getMode);        

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

function sub310_setChartData(dataTbl, allDataTbl){

    if(sub310_getChartMode() === 'year'){
        sub310_setChartDataY(dataTbl, allDataTbl);
    } else {
        sub310_setChartDataM(dataTbl, allDataTbl);
    }

}

function sub310_setChartDataY(dataTbl, allDataTbl){
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
        tmpSuggestedMinY = val['sales'];
        tmpBaseAll = val['sales'];
    });
    
    // 月別来場者数
    $.each(allDataTbl, function(key, val) {
        tmpXLabels.push(key + '年');
        tmpData1.push(val['sales']);
        if (tmpSuggestedMinY > val['sales']){
            tmpSuggestedMinY = val['sales'];
        }
    });

    // Y軸表記最小値計算
    tmpSuggestedMinY = Math.floor(tmpSuggestedMinY / 1000) * 1000 - 500000; 
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
                label: "年間年会費計",
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


function sub310_setChartDataM(dataTbl, allDataTbl){
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

        if(i.toString().padStart(2, '0') in dataTbl){
            tmpData1.push(dataTbl[i.toString().padStart(2, '0')]['sales']);
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
                label: "月間年会費計",
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


function sub310_setDatepicker(getMode){

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
    
        sub310_init_daterangepicker_single_call_gf();
    
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年');
    
    } else {
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        $("#gf_calendar").val(year + '年');
    }

    $("#calendar_saveval").val($("#gf_calendar").val());

}


function sub310_init_daterangepicker_single_call_gf() {

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
                getChartMode:sub310_getChartMode()
            };
        
            sub310_postView(initParam);

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

function sub310_drawTable(dataTbl, allDataTbl){

    if(sub310_getChartMode() === 'year'){
        sub310_drawTableY(dataTbl, allDataTbl);
    } else {
        sub310_drawTableM(dataTbl, allDataTbl);
    }

}

function sub310_drawTableY(dataTbl, allDataTbl){

    var tmpBaseSum = 0;
    var tmpBaseYear = '';

    $("#table_foother").hide();

    // ベースデータの取得
    $.each(dataTbl, function(key, val) {
        tmpBaseYear = key;
        $.each(val, function(key2, val2) {
            if(key2 === 'sales'){
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
        tmp['hikaku'] = tmpBaseSum - val['sales'];
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
            {data:"sales"},
            {data:"hikaku"}
        ]

    } );
}

function sub310_drawTableM(dataTbl, allDataTbl){

    var tmpBaseSum = 0;
    var tmpBaseYear = '';
    $("#default_year").text('前年比');
    $("#table_foother").show();

    // 表データの生成
    var tmpData = [];
    var tmp = [];
    var tmpSalesAll = 0;
    var tmpOldSalesAll = 0;
    var tmpOldSales = 0;

    for(let i = 1; i < 13; i++){
        tmp = [];
        tmp['business_m'] = i.toString() + '月';
        tmpOldSales = 0;

        if(i.toString().padStart(2, '0') in dataTbl){
            tmp['sales'] = dataTbl[i.toString().padStart(2, '0')]['sales'];
            tmpSalesAll += dataTbl[i.toString().padStart(2, '0')]['sales'];
        } else {
            tmp['sales'] = 0;
        }

        if(i.toString().padStart(2, '0') in allDataTbl){
            tmpOldSales = allDataTbl[i.toString().padStart(2, '0')]['sales'];
        } else {
            tmpOldSales = 0;
        }

        tmp['hikaku'] = tmp['sales'] - tmpOldSales;
        tmpOldSalesAll += tmpOldSales;
        tmpData.push(tmp);
    }

//    tmpData.reverse();
    $("#txtAll").text('合計');
    $("#salesAll").text(tmpSalesAll.toString());
    $("#sagakuAll").text((tmpSalesAll - tmpOldSalesAll).toString());


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
            {data:"sales"},
            {data:"hikaku"}
        ]

    } );
}

function sub310_btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 12);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub310_getChartMode()
    };

    $('.input-group.date').datepicker('update', newDate);
    sub310_postView(initParam);

}

function sub310_btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 12);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub310_getChartMode()
    };

    $('.input-group.date').datepicker('update', newDate);

    sub310_postView(initParam);

}

function btnToggleChartMode(){
    // 年間表示／月間表示の切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub310_getChartMode()
    };

    sub310_postView(initParam);

}

// 以下、共通処理
function sub310_getChartMode(){
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
        initFor310();
    });
    
